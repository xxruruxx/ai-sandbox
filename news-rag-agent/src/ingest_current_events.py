import requests
import time
import re
from datetime import date, timedelta
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import chromadb
from bs4 import BeautifulSoup

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "current_events_articles"
USER_AGENT = "GazetteAI/1.0 (https://github.com/xxruruxx/ai-sandbox)"
DAYS_TO_FETCH = 30  # wider backfill since we're rebuilding from scratch

IPTC_TOP_LEVEL = [
    "arts, culture, entertainment and media", "conflict, war and peace",
    "crime, law and justice", "disaster, accident and emergency incident",
    "economy, business and finance", "education", "environment",
    "health", "human interest", "labour", "lifestyle and leisure",
    "politics", "religion", "science and technology", "society",
    "sport", "weather"
]

KNOWN_SECTIONS = [
    "Armed conflicts and attacks", "Arts and culture",
    "Business and economy", "Disasters and accidents",
    "Health and environment", "International relations",
    "Law and crime", "Politics and elections", "Science and technology",
    "Sports", "Deaths"
]


def fetch_day_page_title(target_date):
    month_name = target_date.strftime("%B")
    day = target_date.day
    year = target_date.year
    return f"Portal:Current events/{year} {month_name} {day}"


def fetch_page_text(title):
    headers = {"User-Agent": USER_AGENT}
    params = {"action": "parse", "page": title, "prop": "text", "format": "json"}
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params=params, headers=headers, timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        return None

    html = data.get("parse", {}).get("text", {}).get("*", "")
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def split_into_sections(text):
    """Split raw page text into its real named sections -- this is now
    used for CHUNKING itself (each section becomes its own embedded
    Document), not just for headline generation. This directly fixes
    dilution: a short but real story (e.g. a single-paragraph disaster
    report) no longer gets buried inside a large multi-topic chunk
    alongside unrelated conflict/politics content."""
    pattern = "|".join(re.escape(s) for s in KNOWN_SECTIONS)
    parts = re.split(f"({pattern})", text)

    sections = {}
    current_section = "General"
    for part in parts:
        part = part.strip()
        if part in KNOWN_SECTIONS:
            current_section = part
        elif part:
            sections.setdefault(current_section, "")
            sections[current_section] += part + "\n"

    return sections


def generate_tags(text):
    categories_list = "\n".join(f"- {c}" for c in IPTC_TOP_LEVEL)
    prompt = f"""Read this news summary and select the 1-2 MOST relevant 
categories from this exact list (use the exact wording given):

{categories_list}

Text:
{text[:2000]}

Respond with ONLY the selected category name(s), comma-separated, exactly 
as written above. Nothing else."""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:3b", "prompt": prompt, "stream": False},
            timeout=60
        )
        return response.json()["response"].strip()
    except Exception:
        return ""


def generate_section_headline(section_name, content):
    """One headline for ONE section -- separate API call per section,
    same as before, but now this section IS the actual embedded chunk,
    not just a summary label on top of a larger diluted chunk."""
    if len(content.strip()) < 100:
        return None

    prompt = f"""Read this news section and write ONE short headline 
(under 12 words) covering its most significant story. Be specific -- name 
actual places/events/people ACTUALLY MENTIONED. Do NOT invent anything not 
present.

Section: {section_name}
Text:
{content[:1000]}

Respond with ONLY the headline, nothing else."""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:3b", "prompt": prompt, "stream": False},
            timeout=60
        )
        return response.json()["response"].strip()
    except Exception:
        return None


def get_existing_ids(chroma_collection):
    try:
        existing = chroma_collection.get(include=[])
        return set(existing.get("ids", []))
    except Exception:
        return set()


def main():
    print("Configuring local models (Ollama)...")
    Settings.llm = Ollama(model="qwen2.5:3b", request_timeout=120.0)
    Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

    print("Setting up ChromaDB...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    existing_ids = get_existing_ids(chroma_collection)
    print(f"Existing chunks already in store: {len(existing_ids)}")

    new_documents = []
    today = date.today()

    for days_back in range(DAYS_TO_FETCH):
        target_date = today - timedelta(days=days_back)
        title = fetch_day_page_title(target_date)
        date_str = target_date.isoformat()

        # Check if we've already ingested THIS DATE (any section) --
        # skip the whole day if so, since sections are ingested together
        day_prefix = f"current_events_{date_str}_"
        if any(eid.startswith(day_prefix) for eid in existing_ids):
            continue

        print(f"  Fetching: {title}")
        text = fetch_page_text(title)
        time.sleep(1)

        if not text or len(text.strip()) < 200:
            print(f"    (no real content found for this date, skipping)")
            continue

        tags = generate_tags(text)
        sections = split_into_sections(text)

        day_had_real_section = False
        for section_name, content in sections.items():
            content = content.strip()
            if len(content) < 100:
                continue  # skip thin/boilerplate sections like bare "General"

            headline = generate_section_headline(section_name, content)
            section_slug = re.sub(r'[^a-z0-9]+', '-', section_name.lower()).strip('-')
            doc_id = f"current_events_{date_str}_{section_slug}"

            print(f"    [{section_name}] {headline}")
            day_had_real_section = True

            new_documents.append(
                Document(
                    text=content,
                    doc_id=doc_id,
                    metadata={
                        "date": date_str,
                        "section": section_name,
                        "headline": headline or "",
                        "tags": tags,
                        "link": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        "source": "wikipedia_current_events",
                    },
                )
            )

        if not day_had_real_section:
            print(f"    (no sections met the content threshold, skipping day)")

    if not new_documents:
        print("No new chunks to add. Store is already up to date.")
        return

    print(f"Embedding and storing {len(new_documents)} new section-chunks...")
    VectorStoreIndex.from_documents(new_documents, storage_context=storage_context)

    print(f"Done. {len(new_documents)} new chunks added.")


if __name__ == "__main__":
    main()
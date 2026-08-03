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
DAYS_TO_FETCH = 14

IPTC_TOP_LEVEL = [
    "arts, culture, entertainment and media", "conflict, war and peace",
    "crime, law and justice", "disaster, accident and emergency incident",
    "economy, business and finance", "education", "environment",
    "health", "human interest", "labour", "lifestyle and leisure",
    "politics", "religion", "science and technology", "society",
    "sport", "weather"
]

# Real, recurring section names used by Wikipedia's Current Events Portal
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
    """Pull fully-rendered text for one Current Events Portal day-page.
    Uses action=parse (not the extracts API) because these pages are
    built almost entirely from transcluded templates."""
    headers = {"User-Agent": USER_AGENT}
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
    }
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params=params,
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        return None

    html = data.get("parse", {}).get("text", {}).get("*", "")
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    return text


def split_into_sections(text):
    """Split raw page text into its actual named sections (Armed conflicts,
    Disasters, Sports, etc.) instead of blindly truncating by character
    count -- guarantees later sections aren't silently cut off just because
    an earlier section (usually Armed conflicts) runs long."""
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
    """Classify content against IPTC Media Topics' 17 top-level categories."""
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


def generate_headlines_fallback(text):
    """Used only if section-splitting fails to find any known sections
    (e.g. an unusual page structure) -- old character-limit approach as
    a safety net, not the primary method."""
    prompt = f"""Read this news summary and write UP TO 4 short headlines 
(each under 12 words) covering DIFFERENT major stories. Be specific. Do 
NOT invent anything not present in the text.

Text:
{text[:4000]}

Respond with ONLY the headlines, one per line, nothing else."""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:3b", "prompt": prompt, "stream": False},
            timeout=90
        )
        headlines_raw = response.json()["response"].strip()
        return [h.strip("-• ").strip() for h in headlines_raw.split("\n") if h.strip()][:4]
    except Exception:
        return []


def generate_headlines(text):
    """One headline PER REAL SECTION FOUND that day -- guarantees coverage
    proportional to what actually happened, not an arbitrary fixed count
    or a character-limit guess that silently drops later sections."""
    if len(text.strip()) < 200:
        return []

    sections = split_into_sections(text)

    if not sections or len(sections) <= 1:
        return generate_headlines_fallback(text)

    section_summaries = "\n\n".join(
        f"=== {name} ===\n{content[:800]}" for name, content in sections.items()
    )

    prompt = f"""Below is a day's news, already split into its real sections.

For EACH section shown, write exactly ONE short headline (under 12 words) 
covering that section's most significant story. Be specific -- name actual 
places/events/people ACTUALLY MENTIONED. Do NOT invent anything not present.

{section_summaries}

Respond with ONLY the headlines, one per line, in the format:
[Section Name]: headline text"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:3b", "prompt": prompt, "stream": False},
            timeout=90
        )
        headlines_raw = response.json()["response"].strip()
        headlines = [h.strip("-• ").strip() for h in headlines_raw.split("\n") if h.strip()]
        return headlines[:8]  # section-driven, so allow more than the old fixed 4
    except Exception:
        return []


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
    print(f"Existing day-pages already in store: {len(existing_ids)}")

    new_documents = []
    today = date.today()

    for days_back in range(DAYS_TO_FETCH):
        target_date = today - timedelta(days=days_back)
        title = fetch_day_page_title(target_date)
        doc_id = f"current_events_{target_date.isoformat()}"

        if doc_id in existing_ids:
            continue

        print(f"  Fetching: {title}")
        text = fetch_page_text(title)
        time.sleep(1)

        if not text or not text.strip():
            print(f"    (no content found for this date, skipping)")
            continue

        tags = generate_tags(text)
        headlines = generate_headlines(text)
        headlines_str = " | ".join(headlines)
        print(f"    Tags: {tags}")
        print(f"    Headlines ({len(headlines)}): {headlines_str}")

        new_documents.append(
            Document(
                text=text,
                doc_id=doc_id,
                metadata={
                    "title": title,
                    "date": target_date.isoformat(),
                    "link": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    "source": "wikipedia_current_events",
                    "tags": tags,
                    "headlines": headlines_str,
                },
            )
        )

    if not new_documents:
        print("No new day-pages to add. Store is already up to date.")
        return

    print(f"Embedding and storing {len(new_documents)} new day-pages...")
    VectorStoreIndex.from_documents(new_documents, storage_context=storage_context)

    print(f"Done. {len(new_documents)} new day-pages added. "
          f"Total in store: {len(existing_ids) + len(new_documents)}")


if __name__ == "__main__":
    main()
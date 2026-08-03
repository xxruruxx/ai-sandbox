import requests
import time
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


def fetch_day_page_title(target_date):
    """Wikipedia's Current Events Portal uses dated sub-pages like
    'Portal:Current events/2026 July 17'."""
    month_name = target_date.strftime("%B")
    day = target_date.day
    year = target_date.year
    return f"Portal:Current events/{year} {month_name} {day}"


def fetch_page_text(title):
    """Pull fully-rendered text for one Current Events Portal day-page.
    Uses action=parse (not the extracts API) because these pages are
    built almost entirely from transcluded templates -- the extracts
    API can't see through transclusion and returns empty content."""
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


def generate_tags(text):
    """Classify content against IPTC Media Topics' 17 top-level categories --
    the real industry-standard taxonomy used by AP/Reuters/AFP -- rather than
    free-form tag generation, which drifts in wording across days
    (e.g. "Iran Conflict" vs "Middle East Tensions" for the same topic)."""
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
        tags = response.json()["response"].strip()
        return tags
    except Exception:
        return ""


def generate_headlines(text):
    """3-4 short headlines capturing the day's real spread of stories --
    a single headline understates how much is actually in a typical day's
    coverage (conflict, disaster, politics, health, etc. often all present)."""
    prompt = f"""Read this news summary and write 3-4 short headlines 
(each under 12 words) covering the DIFFERENT major stories of the day -- 
not just the top one. Be specific -- name actual places/events/people, 
not vague categories. Cover distinct topics, not variations of the same story.

Text:
{text[:3000]}

Respond with ONLY the headlines, one per line, nothing else."""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:3b", "prompt": prompt, "stream": False},
            timeout=90
        )
        headlines_raw = response.json()["response"].strip()
        # Split into a clean list, one per line
        headlines = [h.strip("-• ").strip() for h in headlines_raw.split("\n") if h.strip()]
        return headlines[:4]  # cap at 4 even if the model gives more
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
        print(f"    Tags: {tags} | Headline: {headlines_str}")

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
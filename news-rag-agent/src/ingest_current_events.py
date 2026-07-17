import requests
import time
from datetime import date, timedelta
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from bs4 import BeautifulSoup
import chromadb

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "current_events_articles"
USER_AGENT = "GazetteAI/1.0 (https://github.com/xxruruxx/ai-sandbox)"
DAYS_TO_FETCH = 14


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

        new_documents.append(
            Document(
                text=text,
                doc_id=doc_id,
                metadata={
                    "title": title,
                    "date": target_date.isoformat(),
                    "link": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    "source": "wikipedia_current_events",
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
from datasets import load_dataset
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import chromadb

# --- Config ---
SAMPLE_SIZE = 100
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "news_articles"

print("Loading dataset sample...")
ds = load_dataset("abisee/cnn_dailymail", "3.0.0", split=f"train[:{SAMPLE_SIZE}]")

print(f"Converting {len(ds)} articles into documents...")
documents = [
    Document(
        text=row["article"],
        metadata={"id": row["id"], "highlights": row["highlights"]}
    )
    for row in ds
]

print("Configuring local models (Ollama)...")
Settings.llm = Ollama(model="qwen2.5:3b", request_timeout=120.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

print("Setting up ChromaDB...")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

print("Building index (this embeds and stores everything)...")
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context
)

print(f"Done. {len(documents)} articles indexed into '{CHROMA_PATH}'.")

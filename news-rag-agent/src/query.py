from llama_index.core import VectorStoreIndex, Settings, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import chromadb

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "news_articles"

Settings.llm = Ollama(model="qwen2.5:3b", request_timeout=120.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

index = VectorStoreIndex.from_vector_store(vector_store)
query_engine = index.as_query_engine()

question = "What happened with the Minneapolis bridge?"
print(f"Question: {question}\n")

response = query_engine.query(question)
print("Answer:")
print(response)

print("\nSources:")
for node in response.source_nodes:
    print(f"- {node.metadata.get('id', 'unknown')} (score: {node.score:.3f})")
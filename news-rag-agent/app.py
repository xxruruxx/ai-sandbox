import streamlit as st
from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import chromadb

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "news_articles"

st.set_page_config(page_title="News Research Assistant", page_icon="📰")

@st.cache_resource
def load_query_engine():
    Settings.llm = Ollama(model="qwen2.5:3b", request_timeout=120.0)
    Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    index = VectorStoreIndex.from_vector_store(vector_store)
    return index.as_query_engine()

st.title("News Research Assistant")
st.caption("Ask questions about articles in the CNN/DailyMail archive")

query_engine = load_query_engine()

question = st.text_input("Ask a question:", placeholder="What happened with the Minneapolis bridge?")

if st.button("Search") and question:
    with st.spinner("Thinking..."):
        response = query_engine.query(question)

    st.subheader("Answer")
    st.write(str(response))

    st.subheader("Sources")
    for node in response.source_nodes:
        with st.expander(f"Article {node.metadata.get('id', 'unknown')} (relevance: {node.score:.3f})"):
            st.write(node.text[:500] + "...")
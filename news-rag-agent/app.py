import streamlit as st
from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import chromadb

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "news_articles"

st.set_page_config(page_title="News Research Agent", page_icon="📰")

@st.cache_resource
def load_retriever():
    Settings.llm = Ollama(model="qwen2.5:3b", request_timeout=120.0)
    Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    return index.as_retriever(similarity_top_k=3)

retriever = load_retriever()


def grade_relevance(question, nodes, status):
    for node in nodes:
        chunk = node.text[:500]
        prompt = f"""You are checking search results for relevance.

Search query: "{question}"

Retrieved passage:
"{chunk}"

Is this passage relevant to the search query? A passage is relevant if it 
discusses the same event, topic, or subject as the query, even if it doesn't 
answer every detail.

Respond with exactly one word: YES or NO."""
        response = Settings.llm.complete(prompt)
        answer = str(response).strip().upper()
        status.write(f"Checking node (score {node.score:.3f}) -> {answer}")
        if "YES" in answer:
            return True
    return False


def rewrite_query(question, status):
    prompt = f"""The following question did not retrieve relevant results 
from a news article search engine: "{question}"

Rewrite it as a different, more specific search query that might work better.
Return ONLY the rewritten query, nothing else."""
    response = Settings.llm.complete(prompt)
    new_query = str(response).strip()
    status.write(f"Rewriting query -> \"{new_query}\"")
    return new_query


def generate_answer(question, nodes):
    combined_context = "\n\n---\n\n".join([n.text[:800] for n in nodes])
    prompt = f"""Answer the question using only the context below. If the 
context doesn't contain enough information, say so honestly.

Context:
{combined_context}

Question: {question}

Answer:"""
    response = Settings.llm.complete(prompt)
    return str(response).strip()


st.title("News Research Agent")
st.caption("Agentic RAG over CNN/DailyMail archive — retrieves, grades, retries, and answers")

question = st.text_input("Ask a question:", placeholder="What happened with the Minneapolis bridge?")

if st.button("Search") and question:
    max_retries = 2
    current_query = question
    nodes = []
    found_relevant = False

    with st.status("Agent working...", expanded=True) as status:
        for attempt in range(max_retries + 1):
            status.write(f"**Attempt {attempt + 1}:** retrieving for \"{current_query}\"")
            nodes = retriever.retrieve(current_query)
            found_relevant = grade_relevance(current_query, nodes, status)

            if found_relevant:
                status.write("Relevant context found.")
                break
            elif attempt < max_retries:
                current_query = rewrite_query(current_query, status)

        status.update(label="Agent finished", state="complete")

    st.subheader("Answer")
    if found_relevant:
        answer = generate_answer(question, nodes)
        st.write(answer)

        st.subheader("Sources")
        for node in nodes:
            with st.expander(f"Article {node.metadata.get('id', 'unknown')} (relevance: {node.score:.3f})"):
                st.write(node.text[:500] + "...")
    else:
        st.write("I don't have relevant information about this in the corpus.")
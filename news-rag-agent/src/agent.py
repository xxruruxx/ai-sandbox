from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import chromadb

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "news_articles"

Settings.llm = Ollama(model="qwen2.5:3b", request_timeout=120.0)
Settings.embed_model = OllamaEmbedding(model_name = "nomic-embed-text")

chroma_client = chromadb.PersistentClient(path = CHROMA_PATH)
chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
index = VectorStoreIndex.from_vector_store(vector_store)
retriever = index.as_retriever(similarity_top_k=3)


def retrieve(question: str):
    """Retrieve relevant chunks for a question."""
    nodes = retriever.retrieve(question)
    return nodes

def grade_relevance(question: str, nodes) -> bool:
    """
    EXISTENCE CHECK ONLY: returns True as soon as ANY retrieved node is
    judged relevant. This does not filter which chunks get used for the
    final answer -- it only decides whether to proceed to generation or
    trigger a query rewrite + retry.

    NOTE: small local models (e.g. Qwen2.5:3b) can be inconsistent at 
    binary relevance judgments -- the same underlying content may be 
    graded differently across calls, even with similar similarity scores. 
    Grading is treated as a useful heuristic signal, not a guarantee.
    """
    for node  in nodes:
        chunk = node.text[:500]
        prompt = f""" You are checking search results for relevance.

Search query: "{question}"

Retrieved passage:
"{chunk}"

Is this passage relevant to the search query? A passage is relevant if it
discusses the same event, topic, or subject as the query, even if it doesn't
answer every detail.

Respond with exactly one word: YES or NO."""
        
        response = Settings.llm.complete(prompt)
        answer = str(response).strip().upper()
        print(f" [grade_relevance] Node (score {node.score: .3f}) -> {answer}")
        if "YES" in answer:
            return True
    return False


def rewrite_query(question: str) -> str:
    """Ask the LLM to reformulate the question for better retrieval."""
    prompt = f""" The following question did not retrieve relevant results
    from a news article search engine: "{question}"

Rewrite it as a different, more specific search query that might work better. 
Return ONLY the rewritten query, nothing else."""
    
    response = Settings.llm.complete(prompt)
    new_query = str(response).strip()
    print(f" [rewrite_query] Rewritten to: {new_query}")
    return new_query


def generate_answer(question: str, nodes) -> str:
    """
    Combine ALL retrieved node contexts (not just the graded one) into a 
    single context block, then generate the final synthesized answer.
    """
    combined_context = "\n\n---\n\n".join([n.text[:800] for n in nodes])

    prompt = f"""Answer the question using only the context below. If the
context doesn't contain enough information, say so honestly.

Context:
{combined_context}

Question: {question}

Answer:"""
    
    response = Settings.llm.complete(prompt)
    return str(response).strip()


# --- Full agentic loop test ---
if __name__ == "__main__":
    q = "What happened with the Minneapolis bridge?"
    print(f"Question: {q}")

    max_retries = 2
    current_query = q
    nodes = []
    found_relevant = False

    for attempt in range(max_retries + 1):
        print(f"--- Attempt {attempt + 1} ---")
        nodes = retrieve(current_query)
        found_relevant = grade_relevance(current_query, nodes)

        if found_relevant:
            break
        elif attempt < max_retries:
            current_query = rewrite_query(current_query)
        print()

    print("\n--- Final Answer ---")
    if found_relevant:
        answer = generate_answer(q, nodes)
        print(answer)
    else:
        print("I don't have relevant information about this in the corpus.")


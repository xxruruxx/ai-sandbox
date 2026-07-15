from typing import TypedDict, Literal
import json

from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import chromadb

from langgraph.graph import StateGraph, END

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "news_articles"

Settings.llm = Ollama(model="qwen2.5:3b", request_timeout=120.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
index = VectorStoreIndex.from_vector_store(vector_store)
retriever = index.as_retriever(similarity_top_k=3)


# ---- Agent state: what flows through the graph ----
class AgentState(TypedDict):
    original_question: str
    current_query: str
    nodes: list
    relevant_nodes: list       # only chunks the LLM actually judged relevant
    attempts: int
    max_attempts: int
    action: str                 # the LLM's own chosen next action
    action_reason: str
    final_answer: str


# ---- Nodes ----

def retrieve_node(state: AgentState) -> AgentState:
    nodes = retriever.retrieve(state["current_query"])
    state["nodes"] = nodes
    return state


def grade_node(state: AgentState) -> AgentState:
    relevant = []
    for node in state["nodes"]:
        chunk = node.text[:500]
        prompt = f"""Question: "{state['current_query']}"

Passage:
"{chunk}"

Is this passage relevant to the question? Answer YES or NO only."""
        response = Settings.llm.complete(prompt)
        answer = str(response).strip().upper()
        print(f"  [grade] node score={node.score:.3f} -> {answer}")
        if "YES" in answer:
            relevant.append(node)
    print(f"  [grade] total relevant found: {len(relevant)} / {len(state['nodes'])}")
    state["relevant_nodes"] = relevant
    return state


def decide_node(state: AgentState) -> AgentState:
    found = len(state["relevant_nodes"])
    attempts_left = state["max_attempts"] - state["attempts"]

    prompt = f"""You are an AI research agent deciding your next action.

Original question: "{state['original_question']}"
Current search query: "{state['current_query']}"
Relevant passages found so far: {found}
Retry attempts remaining: {attempts_left}

Choose exactly ONE next action:
- "answer": you have enough relevant context to answer the question
- "rewrite_query": no relevant context found, try a reformulated search
- "give_up": no relevant context found and no attempts remain, admit you don't know

Respond ONLY as JSON: {{"action": "...", "reason": "..."}}"""

    response = str(Settings.llm.complete(prompt)).strip()
    print(f"  [decide] raw response: {response}")

    try:
        json_str = response[response.index("{"):response.rindex("}") + 1]
        decision = json.loads(json_str)
        llm_action = decision.get("action", "give_up")
        llm_reason = decision.get("reason", "")
    except Exception as e:
        print(f"  [decide] JSON parse failed: {e}")
        llm_action = "answer" if found > 0 else "give_up"
        llm_reason = "fallback: could not parse model decision"

    # Guard: the model can misjudge things Python already knows for certain.
    # If relevant context genuinely exists, "answer" is always correct --
    # override any contradictory LLM decision rather than trust a small
    # model's arithmetic over ground truth we already computed.
    if found > 0 and llm_action != "answer":
        print(f"  [decide] OVERRIDE: model said '{llm_action}' but {found} relevant "
              f"chunk(s) exist -- forcing 'answer' (model reasoning was factually wrong)")
        llm_action = "answer"
        llm_reason = f"[corrected] {found} relevant chunk(s) found; overriding model's contradictory decision"

    state["action"] = llm_action
    state["action_reason"] = llm_reason
    print(f"  [decide] final action={state['action']} | reason={state['action_reason']}")
    return state


def rewrite_node(state: AgentState) -> AgentState:
    prompt = f"""This search query found no relevant results: "{state['current_query']}"

Rewrite it as a more specific query. Return ONLY the rewritten query."""
    response = Settings.llm.complete(prompt)
    state["current_query"] = str(response).strip()
    state["attempts"] += 1
    return state


def generate_node(state: AgentState) -> AgentState:
    context = "\n\n---\n\n".join([n.text[:800] for n in state["relevant_nodes"]])
    prompt = f"""Answer using only this context. Be accurate and concise.

Context:
{context}

Question: {state['original_question']}

Answer:"""
    response = Settings.llm.complete(prompt)
    state["final_answer"] = str(response).strip()
    return state


def give_up_node(state: AgentState) -> AgentState:
    state["final_answer"] = "I don't have relevant information about this in the corpus."
    return state


# ---- Routing: reads the LLM's own decision, not a hardcoded threshold ----
def route_after_decision(state: AgentState) -> Literal["generate", "rewrite", "give_up"]:
    if state["action"] == "answer":
        return "generate"
    elif state["action"] == "rewrite_query" and state["attempts"] < state["max_attempts"]:
        return "rewrite"
    else:
        return "give_up"


# ---- Build the graph ----
graph = StateGraph(AgentState)

graph.add_node("retrieve", retrieve_node)
graph.add_node("grade", grade_node)
graph.add_node("decide", decide_node)
graph.add_node("rewrite", rewrite_node)
graph.add_node("generate", generate_node)
graph.add_node("give_up", give_up_node)

graph.set_entry_point("retrieve")
graph.add_edge("retrieve", "grade")
graph.add_edge("grade", "decide")
graph.add_conditional_edges("decide", route_after_decision, {
    "generate": "generate",
    "rewrite": "rewrite",
    "give_up": "give_up",
})
graph.add_edge("rewrite", "retrieve")   # loop back
graph.add_edge("generate", END)
graph.add_edge("give_up", END)

app = graph.compile()


# ---- Run it ----
if __name__ == "__main__":
    initial_state = {
        "original_question": "What happened with the Minneapolis bridge?",
        "current_query": "What happened with the Minneapolis bridge?",
        "nodes": [],
        "relevant_nodes": [],
        "attempts": 0,
        "max_attempts": 2,
        "action": "",
        "action_reason": "",
        "final_answer": "",
    }

    result = app.invoke(initial_state)
    print("\n--- Final Answer ---")
    print(result["final_answer"])
# ai-sandbox

Personal space for AI/ML experiments and applied projects.

## Projects

### news-rag-agent
Agentic RAG research assistant over a news article corpus (CNN/DailyMail dataset).

**Stack:** LlamaIndex, ChromaDB, LangGraph, Ollama (Qwen2.5:3b for reasoning, nomic-embed-text for embeddings), Streamlit

**Status:** Baseline pipeline working — articles are chunked, embedded, and stored in a local vector store; queries retrieve relevant articles and generate grounded answers via a local LLM.

**Design notes:**
- Model sizes chosen based on local hardware constraints (8GB RAM) — Qwen2.5:3b balances quality and resource usage
- Uses a dedicated embedding model (nomic-embed-text) rather than the chat model, for better retrieval quality
- Static dataset (CNN/DailyMail) chosen deliberately over live scraping to validate core RAG/agentic logic before adding a live ingestion layer

**Next steps:** agentic reasoning loop (LangGraph) for multi-hop retrieval and query refinement, Streamlit UI

### playwright-scraper
Browser automation pipeline for structured property listing data (Pag-IBIG Online Public Auction).

**Stack:** Playwright (Python)

**Status:** Confirmed page navigation and cascading filter interaction (Region → Province dropdown).

**Design notes:**
- Includes retry/backoff logic to handle rate limiting respectfully
- Scoped to factual/transactional public listing data, not copyrighted editorial content

**Next steps:** complete City/Municipality filter chain, extract listing data, export to CSV

## Setup

```powershell
python -m venv rag-env
.\rag-env\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Requires [Ollama](https://ollama.com) installed locally, with models pulled:
```powershell
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```
# News Research Assistant

An agentic RAG (Retrieval-Augmented Generation) system that answers questions about a corpus of news articles (CNN/DailyMail dataset), running entirely on local infrastructure — no external API calls, no cost.

## What it does

Ask a natural language question about the news archive, and the system retrieves the most relevant articles, then generates a grounded answer citing which sources it used.

## Stack

- **Ollama** — local model serving
- **Qwen2.5:3b** — reasoning/answer generation
- **nomic-embed-text** — embeddings (separate from the reasoning model, for better retrieval quality)
- **LlamaIndex** — document ingestion, chunking, retrieval orchestration
- **ChromaDB** — local vector store
- **Streamlit** — web UI

## Design notes

- Model sizes were chosen based on local hardware constraints (8GB RAM)
- Static dataset (CNN/DailyMail) used to validate core retrieval/reasoning before adding a live data ingestion layer
- Fully local — runs without internet access once models and data are downloaded, and incurs no API costs

## Limitations

- Relevance grading uses a small local LLM (Qwen2.5:3b) for binary 
  YES/NO judgments, which can be inconsistent across similar or even 
  near-identical content. This is a known tradeoff of running fully 
  local on constrained hardware (8GB RAM) rather than using a larger 
  model or hosted API.

## Setup

**1. Install Ollama** and pull the required models:
```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

**2. Create a virtual environment and install dependencies:**
```bash
python -m venv rag-env
# Windows:
.\rag-env\Scripts\Activate.ps1
# Mac/Linux:
source rag-env/bin/activate

pip install -r requirements.txt
```

**3. Ingest the dataset** (downloads CNN/DailyMail sample, embeds, and stores in ChromaDB):
```bash
python src/ingest.py
```

**4. Run the app:**
```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

## Status

Baseline RAG pipeline complete (ingest, retrieve, answer, source attribution via Streamlit UI).

**Next:** agentic reasoning layer (LangGraph) for query refinement and multi-hop retrieval.
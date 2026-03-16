# EDGAR RAG

RAG system over SEC EDGAR filings. Answers business questions grounded in 10-K/10-Q filing data from 246 companies.

## Architecture

```
backend/
  config.py              - env config (loads .env)
  db.py                  - postgres + pgvector schema & helpers
  api.py                 - FastAPI server (also serves the UI)
  evaluate.py            - LLM-as-a-judge benchmark for RAG quality
  ingestion/
    parser.py            - XBRL cleanup, HTML stripping, metadata extraction
    chunker.py           - token-aware chunking with TOC-aware section splitting
    pipeline.py          - offline ingestion orchestrator (idempotent, resumable)
  retrieval/
    embeddings.py        - OpenAI text-embedding-3-small
    search.py            - hybrid search: pgvector cosine + pg_trgm, merged via RRF
    query_decomposer.py  - query decomposition + expansion (gpt-5-nano)
  ai_clients/
    base.py              - abstract AI client interface
    openai_client.py     - OpenAI streaming implementation
  chat/
    prompts/             - modular system, user, and decomposer prompt templates
    sessions.py          - postgres-backed chat session management
ui/
  index.html             - chat interface (served by FastAPI at /)
  styles.css
  app.js
```

## Prerequisites

- [Docker](https://www.docker.com/) — for Postgres with pgvector
- [uv](https://docs.astral.sh/uv/) — Python package manager (`brew install uv` or `pip install uv`)
- OpenAI API key with access to `gpt-5.3`, `gpt-5-nano`, and `text-embedding-3-small`

## Setup & Running

```bash
# 1. Copy env and fill in your OpenAI key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
# Set up the path to the edgar_corpus directory in the .env file (CORPUS_DIR)
# an easy set up is to copy the edgar_corpus directory to the root directory and set CORPUS_DIR=edgar_corpus

# 2. Start Postgres with pgvector
docker compose up -d

# 3. Install Python dependencies
uv sync

# 4. Run the ingestion pipeline
#    Processes all 246 filings in edgar_corpus/ into the vector DB.
#    Idempotent — safe to re-run; already-processed documents are skipped.
uv run python -m backend.ingestion.pipeline

# 5. Start the server + UI
uv run python -m backend.api

# 6. (Optional) Run benchmarks
uv run python -m backend.evaluate
```

**Open [http://localhost:8000](http://localhost:8000) in your browser.**

The FastAPI server serves the chat UI directly — no separate UI server or build step is needed.

## Evaluation

The project includes an automated evaluation suite in `backend/evaluate.py` that uses an **LLM-as-a-judge** approach to grade RAG performance. 

- **Metrics**: Grades Context Relevance, Groundedness, and Completeness on a 1-5 scale.
- **Comparison**: Benchmarks the "Baseline" (raw query) against the "Advanced" (decomposed + ticker-filtered) retrieval paths.
- **Results**: Our benchmarks show that decomposition significantly improves **Completeness** (from 3.3 to 4.0) and **Groundedness** (from 3.5 to 3.9) for complex financial queries.

Detailed results are available in [eval.md](eval.md).

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/edgar_rag` | Postgres connection string |
| `LLM_MODEL` | `gpt-5.3` | Model used for answer generation |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Model used for embeddings |
| `DECOMPOSE_MODEL` | `gpt-5-nano` | Model used for query decomposition |
| `CORPUS_DIR` | `edgar_corpus` | Directory containing the filing markdown files |

## Design Decisions

**Text Cleanup**: EDGAR filings contain XBRL inline data, HTML tags, and machine-readable identifiers. The parser strips all non-prose content and removes Table of Contents entries to keep only readable text.

**Chunking**: TOC-aware splitting at section boundaries, falling back to paragraph boundaries (2500 tokens). Chunks below a minimum token count are merged or discarded. Each chunk is prepended with a metadata header (company, ticker, type, date, quarter) so the embedding and LLM always retain source context.

**Query Decomposition + Expansion**: Complex queries are broken into sub-queries by `gpt-5-nano` using **OpenAI Structured Outputs**. It extracts explicit stock tickers and implied entities, which are used to pre-filter PostgreSQL results, dramatically reducing noise from unrelated companies' filings.

**Hybrid Retrieval (RRF)**: Combines pgvector cosine similarity with PostgreSQL trigram matching via Reciprocal Rank Fusion. Vector search captures semantic meaning; trigram search catches exact ticker/company name matches and financial terms.

**Streaming**: Single LLM call (`gpt-5.3`) with streaming via Server-Sent Events. The answer is produced in one API request with real-time token delivery to the UI.

**Session Memory**: Chat history stored in Postgres. Sessions can be created, loaded, and deleted from the sidebar. Message history is included in the prompt context for follow-up questions.

## Request Flow

```
User Question
    |
    v
Query Decomposer (gpt-5-nano)         --> extract tickers + sub-queries (Pydantic)
    |                                      (pre-filters doc set by ticker)
    v
Hybrid Retrieval (per sub-query)       --> pgvector cosine + pg_trgm keyword
    |                                      merged via RRF, deduplicated
    v
Prompt Assembly                        --> system prompt + chunks + question
    v
LLM (gpt-5.3, single streaming call)
    v
Streamed Answer with Source Citations
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | Stream a chat response (SSE) |
| `GET` | `/api/sessions` | List all sessions |
| `POST` | `/api/sessions` | Create a new session |
| `GET` | `/api/sessions/{id}/messages` | Get messages for a session |
| `DELETE` | `/api/sessions/{id}` | Delete a session |

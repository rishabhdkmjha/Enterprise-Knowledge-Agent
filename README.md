# Enterprise AI Knowledge Agent

An AI assistant that answers questions from **PDFs, technical documents and a business database**. It calls its tools through the
**Model Context Protocol (MCP)**, **verifies its own answers** against the retrieved evidence, and **cites its sources**.

Built with Python, FastAPI, LangGraph, PostgreSQL + pgvector, MCP and React.

<!-- Add a screenshot: save it as docs/screenshot.png and uncomment the next line -->
<!-- ![Demo](docs/screenshot.png) -->

## Features

- **Hybrid retrieval**: pgvector cosine similarity + Postgres full-text search, merged with Reciprocal Rank Fusion
- **Multi-source answers**: uploaded PDF / TXT / MD documents and a read-only SQL database, even in a single question
- **MCP tool layer**: the agent reaches data only through an MCP server (`search_documents`, `query_database`, `describe_database`, `list_sources`)
- **Agentic workflow (LangGraph)**: plan -> retrieve -> generate -> verify, with a self-correcting retry loop
- **Answer verification**: a fact-checking step marks each answer `verified` or `low confidence`
- **Citations**: every claim links to a source file and page, or to the exact SQL query (`[DB]`)
- **Self-correcting SQL**: a failed query is repaired once using the database error message
- **Evaluation harness**: measures citation accuracy, answer accuracy, verified rate and latency
- **React UI**: upload documents, chat, inspect citations and the agent's reasoning trace

## Architecture

```
React UI --> FastAPI (/ask, /ingest, /sources)
                |
                v
        LangGraph agent
   plan --> retrieve --> generate --> verify --+--> answer
              ^                                 |
              +------ not grounded (retry) -----+
                |
                v  (MCP client, stdio)
        MCP server: search_documents | query_database | describe_database | list_sources
                |
                v
        PostgreSQL + pgvector  (chunks, embeddings, full-text index, business tables)
```

| Layer | Technology |
|-------|------------|
| LLM | Groq, `openai/gpt-oss-120b` (configurable) via LangChain |
| Orchestration | LangGraph |
| Tool protocol | MCP (official Python SDK 1.x, stdio transport) |
| Embeddings | `BAAI/bge-small-en-v1.5` via fastembed (local, 384-dim) |
| Storage | PostgreSQL 16 + pgvector (HNSW + GIN indexes) |
| API | FastAPI |
| UI | React + Vite |
| Deployment | Docker Compose |

## Quick start

**Prerequisites:** Python 3.11+, Node 18+, a free [Groq API key](https://console.groq.com), and either Docker Desktop
or a hosted Postgres with pgvector (Neon or Supabase).

> Keep the project outside OneDrive-synced folders. Syncing `node_modules` and `.venv` makes installs very slow and can lock files.

```powershell
# 1. Database (Docker). If you use a hosted Postgres, set DATABASE_URL in backend/.env instead and skip this.
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                # then put your GROQ_API_KEY inside .env
uvicorn app.main:app --port 8000      # wait for "Application startup complete"

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

The first start downloads the embedding model (about 70 MB) and seeds two sample policies plus a demo `employees` table.
To run the database and API together in Docker instead: `docker compose up --build` (then only the frontend runs locally).

### Configuration (`backend/.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | none | Required for `/ask` |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Any Groq model with tool calling / structured output |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/knowledge` | Postgres with the pgvector extension |

Groq retires models regularly. If `/ask` fails with `model_not_found`, list the models your key can use
(`https://api.groq.com/openai/v1/models`) and update `LLM_MODEL`.

## Try it

Upload `test_data/acme_policies.pdf` in the sidebar, then ask:

- *How many days per week can employees work remotely without approval?* -> answer with a page citation
- *How many leave days has Vikram Singh taken?* -> answered from the database, SQL shown as `[DB]`
- *What is the company dress code?* -> says it doesn't have the information instead of guessing

More cases with expected answers: [`test_data/TEST_QUESTIONS.md`](test_data/TEST_QUESTIONS.md).

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/sources` | Ingested documents and chunk counts |
| `POST` | `/ingest` | Upload a `.pdf`, `.txt` or `.md` file (multipart field `file`) |
| `POST` | `/ask` | `{"question": "..."}` returns `{answer, grounded, citations[], trace[]}` |

## Evaluation

```powershell
pip install httpx
python eval/run_eval.py                          # sample docs + database
python eval/run_eval.py eval/dataset_pdf.json    # after uploading acme_policies.pdf
```

The script reports citation accuracy, answer accuracy, verified rate and average latency. Add your own cases to the JSON files:
each has a `question`, an `expected_source` (or `null` for unanswerable questions) and `keywords_any`.

<!-- Paste your own eval output here, for example:
citation accuracy 4/4 | answer accuracy 4/4 | verified 4/4 | avg latency 3.2s -->

## Design decisions

- **Hybrid search over pure vector search**: exact terms (names, policy numbers, "P1") match through full-text search, meaning through embeddings; RRF merges both without score tuning.
- **MCP instead of direct function calls**: tools are decoupled from the agent and reusable by any MCP client.
- **Verification loop**: a separate fact-check pass catches unsupported claims, and the agent retries once with a rewritten query.
- **Safe SQL tool**: SELECT only, single statement, read-only transaction, 3 s timeout, restricted schema, keyword blocklist.
- **Prompt-injection hygiene**: retrieved text is passed as data, with an explicit rule never to follow instructions found in evidence.

## Project structure

```
backend/
  app/
    main.py          FastAPI app and lifespan (DB init, seeding, MCP session)
    graph.py         LangGraph agent: plan / retrieve / generate / verify
    mcp_server.py    MCP tools (stdio)
    mcp_client.py    long-lived MCP client session
    db.py            schema, hybrid search, read-only SQL runner
    ingest.py        PDF/text extraction, chunking, embedding, storage
    embeddings.py    local embedding model
    config.py        environment configuration
  debug_mcp.py       standalone check that the MCP server starts and answers
  sample_docs/       demo policies (auto-seeded)
frontend/            React + Vite UI
eval/                evaluation harness and datasets
test_data/           test PDF and manual test checklist
docker-compose.yml   Postgres (pgvector) + API
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `docker compose` cannot reach the Docker API | Start Docker Desktop and wait for "Engine running" |
| `MCP Connection closed` / `No module named 'mcp.server.fastmcp'` | You have MCP 2.x. Run `pip install "mcp>=1.9,<2"` |
| Check the MCP server on its own | `python debug_mcp.py` from `backend/` should list 4 tools |
| `ERR_EMPTY_RESPONSE` or "socket hang up" | A stale process holds port 8000. Find it with `netstat -ano \| findstr :8000`, stop it with `taskkill /PID <number> /F` (or stop a Docker `api` container), then restart uvicorn |
| `model_not_found` from Groq | Set a currently available model in `LLM_MODEL` (see Configuration) |
| `Cannot find module @rollup/rollup-win32-x64-msvc` | Delete `node_modules` and `package-lock.json`, then run `npm install` |
| huggingface symlink warning on Windows | Harmless, ignore it |

## Roadmap

- [ ] Streaming responses (SSE)
- [ ] Cross-encoder re-ranking after hybrid retrieval
- [ ] Authentication and per-user document access
- [ ] OCR for scanned PDFs
- [ ] Conversation memory across turns
- [ ] GitHub Actions: run the eval on every push

SQL guardrails are regex-based. For production, connect with a dedicated read-only database role.

## License

MIT

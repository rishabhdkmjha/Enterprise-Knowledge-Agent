# Enterprise AI Knowledge Agent

RAG + MCP + LangGraph. Answers from PDFs/docs (pgvector hybrid search) and a business database (read-only SQL),
calls everything through an MCP server, verifies its own answer, and cites evidence.

```
React UI -> FastAPI /ask -> LangGraph: plan -> retrieve -> generate -> verify -(not grounded)-> retrieve (retry once)
                                         |
                                  MCP client (stdio) -> MCP server: search_documents | query_database | describe_database | list_sources
                                                                         |
                                                              PostgreSQL + pgvector
```

## Run (Windows PowerShell)
```powershell
# 1. database
docker compose up -d db

# 2. backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # put your GROQ_API_KEY in .env
uvicorn app.main:app --reload --port 8000

# 3. frontend (new terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173

# 4. evaluate (new terminal, venv active)
pip install httpx
python eval/run_eval.py
```
Or run DB + API together: `docker compose up --build` (then only the frontend runs locally).

Sample docs in `backend/sample_docs` and a demo `biz.employees` table are auto-seeded on first start.

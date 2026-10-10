from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db
from .graph import answer_question
from .ingest import ingest_bytes
from .mcp_client import tools

SAMPLES = Path(__file__).resolve().parent.parent / "sample_docs"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if not db.list_sources():  # seed demo docs so the pipeline works out of the box
        for f in SAMPLES.glob("*"):
            ingest_bytes(f.name, f.read_bytes())
    await tools.start()
    yield
    await tools.stop()


app = FastAPI(title="Enterprise Knowledge Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])


class Ask(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/sources")
async def sources():
    return await run_in_threadpool(db.list_sources)


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, "Only .pdf, .txt, .md supported")
    try:
        n = await run_in_threadpool(ingest_bytes, file.filename, await file.read())
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"name": file.filename, "chunks": n}


@app.post("/ask")
async def ask(body: Ask):
    if not body.question.strip():
        raise HTTPException(400, "Empty question")
    try:
        return await answer_question(body.question)
    except Exception as e:
        raise HTTPException(500, f"Agent failed: {e}")

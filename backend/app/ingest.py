import io
import sys
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from .db import connect
from .embeddings import embed

splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)


def extract_pages(name: str, data: bytes) -> list[tuple[int, str]]:
    if name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    return [(1, data.decode("utf-8", errors="ignore"))]


def ingest_bytes(name: str, data: bytes) -> int:
    chunks = [(pg, t) for pg, txt in extract_pages(name, data) for t in splitter.split_text(txt) if t.strip()]
    if not chunks:
        raise ValueError("No extractable text found in file")
    vecs = embed([t for _, t in chunks])
    with connect() as conn:
        conn.execute("DELETE FROM documents WHERE name=%s", (name,))
        doc_id = conn.execute("INSERT INTO documents(name) VALUES (%s) RETURNING id", (name,)).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks(doc_id,page,content,embedding) VALUES (%s,%s,%s,%s)",
                [(doc_id, pg, t, v) for (pg, t), v in zip(chunks, vecs)])
    return len(chunks)


if __name__ == "__main__":  # python -m app.ingest path1 path2 ...
    for p in sys.argv[1:]:
        print(p, ingest_bytes(Path(p).name, Path(p).read_bytes()), "chunks")

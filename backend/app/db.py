import re

import psycopg
from pgvector.psycopg import register_vector

from .config import DATABASE_URL, EMBED_DIM

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS chunks (
  id SERIAL PRIMARY KEY,
  doc_id INT REFERENCES documents(id) ON DELETE CASCADE,
  page INT, content TEXT NOT NULL,
  embedding vector({EMBED_DIM}),
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED);
CREATE INDEX IF NOT EXISTS chunks_emb_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE SCHEMA IF NOT EXISTS biz;
CREATE TABLE IF NOT EXISTS biz.employees (
  id SERIAL PRIMARY KEY, name TEXT, department TEXT, role TEXT,
  annual_leave_days INT, leave_taken INT);
"""

SEED = [
    ("Asha Rao", "Engineering", "Backend Engineer", 24, 10),
    ("Vikram Singh", "Engineering", "ML Engineer", 24, 18),
    ("Neha Gupta", "HR", "HR Manager", 28, 5),
    ("Rahul Mehta", "Sales", "Account Executive", 20, 20),
]

HYBRID_SQL = """
WITH vec AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY dist) AS rk FROM (
    SELECT id, embedding <=> %(q)s AS dist FROM chunks ORDER BY dist LIMIT 20) a),
kw AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY r DESC) AS rk FROM (
    SELECT id, ts_rank_cd(tsv, websearch_to_tsquery('english', %(t)s)) AS r
    FROM chunks WHERE tsv @@ websearch_to_tsquery('english', %(t)s)
    ORDER BY r DESC LIMIT 20) b)
SELECT c.id, d.name, c.page, c.content,
  COALESCE(1.0/(60+vec.rk),0) + COALESCE(1.0/(60+kw.rk),0) AS score
FROM chunks c JOIN documents d ON d.id = c.doc_id
LEFT JOIN vec ON vec.id = c.id LEFT JOIN kw ON kw.id = c.id
WHERE vec.id IS NOT NULL OR kw.id IS NOT NULL
ORDER BY score DESC LIMIT %(n)s
"""

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|truncate|copy|public|information_schema)\b|\bpg_|;", re.I
)


def connect():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    register_vector(conn)
    return conn


def init_db():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(SCHEMA)
        if conn.execute("SELECT count(*) FROM biz.employees").fetchone()[0] == 0:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO biz.employees(name,department,role,annual_leave_days,leave_taken) "
                    "VALUES (%s,%s,%s,%s,%s)", SEED)


def list_sources() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT d.name, count(c.id) FROM documents d LEFT JOIN chunks c ON c.doc_id=d.id "
            "GROUP BY d.name ORDER BY d.name").fetchall()
    return [{"name": n, "chunks": k} for n, k in rows]


def hybrid_search(text: str, vec, k: int = 5) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(HYBRID_SQL, {"q": vec, "t": text, "n": k}).fetchall()
    return [{"id": r[0], "name": r[1], "page": r[2], "content": r[3], "score": float(r[4])} for r in rows]


def describe_schema() -> str:
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema='biz' ORDER BY table_name, ordinal_position").fetchall()
    tables: dict[str, list[str]] = {}
    for t, c, d in rows:
        tables.setdefault(t, []).append(f"{c} {d}")
    return "\n".join(f"{t}({', '.join(cols)})" for t, cols in tables.items())


def run_readonly_sql(sql: str) -> dict:
    s = sql.strip()
    if not re.match(r"^(select|with)\b", s, re.I) or _FORBIDDEN.search(s):
        return {"error": "Only single read-only SELECT queries on business tables are allowed."}
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.read_only = True
            conn.execute("SET LOCAL statement_timeout = 3000")
            conn.execute("SET LOCAL search_path = biz")
            cur = conn.execute(s)
            cols = [d.name for d in cur.description]
            rows = [list(r) for r in cur.fetchmany(50)]
        return {"columns": cols, "rows": rows}
    except Exception as e:  # surface SQL errors so the agent can self-correct
        return {"error": str(e).splitlines()[0]}

"""MCP server (stdio) exposing knowledge tools. Never print to stdout here."""
import json

from mcp.server.fastmcp import FastMCP

from . import db
from .embeddings import embed

mcp = FastMCP("knowledge-tools")


@mcp.tool()
def list_sources() -> str:
    """List ingested documents and their chunk counts (JSON)."""
    return json.dumps(db.list_sources())


@mcp.tool()
def search_documents(query: str, top_k: int = 5) -> str:
    """Hybrid vector + keyword search over ingested documents. Returns JSON list of chunks with source name and page."""
    return json.dumps(db.hybrid_search(query, embed([query])[0], top_k))


@mcp.tool()
def describe_database() -> str:
    """Describe the business database tables and columns (JSON string)."""
    return json.dumps(db.describe_schema())


@mcp.tool()
def query_database(sql: str) -> str:
    """Run ONE read-only SELECT against the business database. Returns JSON {columns, rows} or {error}."""
    return json.dumps(db.run_readonly_sql(sql), default=str)


if __name__ == "__main__":
    embed(["warmup"])
    mcp.run()

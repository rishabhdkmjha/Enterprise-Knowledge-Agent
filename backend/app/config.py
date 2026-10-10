import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/knowledge")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
MAX_RETRIES = 1  # verify -> re-retrieve loops

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/edgar_rag")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.3")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
DECOMPOSE_MODEL = os.getenv("DECOMPOSE_MODEL", "gpt-5-nano")
CORPUS_DIR = os.getenv("CORPUS_DIR", "edgar_corpus")
# Legacy; narrative chunking uses NARRATIVE_CHUNK_SIZE and CHUNK_OVERLAP_PCT
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
# Section-aware chunking
NARRATIVE_CHUNK_SIZE = int(os.getenv("NARRATIVE_CHUNK_SIZE", "2000"))
CHUNK_OVERLAP_PCT = float(os.getenv("CHUNK_OVERLAP_PCT", "0.15"))
TABLE_MAX_TOKENS = int(os.getenv("TABLE_MAX_TOKENS", "2000"))
FOOTNOTE_MAX_TOKENS = int(os.getenv("FOOTNOTE_MAX_TOKENS", "2000"))
EMBEDDING_DIMS = 1536

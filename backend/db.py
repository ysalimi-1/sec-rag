import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from backend.config import DATABASE_URL, EMBEDDING_DIMS

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            DATABASE_URL, 
            min_size=1, 
            max_size=10, 
            kwargs={"row_factory": dict_row},
            open=False
        )
        await _pool.open()
    return _pool


def get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db(overwrite: bool = False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if overwrite:
                cur.execute("DROP TABLE IF EXISTS messages, sessions, chunks, documents CASCADE")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename TEXT UNIQUE NOT NULL,
                    company TEXT,
                    ticker TEXT,
                    filing_type TEXT,
                    filing_date TEXT,
                    quarter TEXT,
                    cik TEXT
                )
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER,
                    content TEXT,
                    embedding vector({EMBEDDING_DIMS}),
                    section TEXT,
                    token_count INTEGER
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    title TEXT DEFAULT 'New Chat',
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)

            # Drop old GIN index and create GIST for distance-based ordering
            cur.execute("DROP INDEX IF EXISTS idx_chunks_content_trgm")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm_gist
                ON chunks USING gist (content gist_trgm_ops)
            """)

        conn.commit()

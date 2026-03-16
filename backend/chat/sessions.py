from backend.db import get_conn


def create_session(title: str = "New Chat") -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (title) VALUES (%s) RETURNING id, title, created_at",
                (title,),
            )
            row = cur.fetchone()
        conn.commit()
    return row


def list_sessions() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC")
            return cur.fetchall()


def get_messages(session_id: int) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, role, content, created_at FROM messages WHERE session_id = %s ORDER BY created_at",
                (session_id,),
            )
            return cur.fetchall()


def add_message(session_id: int, role: str, content: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s) RETURNING id, role, content, created_at",
                (session_id, role, content),
            )
            row = cur.fetchone()
            cur.execute("UPDATE sessions SET updated_at = now() WHERE id = %s", (session_id,))
        conn.commit()
    return row


def delete_session(session_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        conn.commit()

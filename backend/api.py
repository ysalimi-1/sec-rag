import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.db import init_db
from backend.retrieval import decompose_and_expand, retrieve_multi
from backend.chat import SYSTEM_PROMPT, build_user_prompt
from backend.chat import sessions
from backend.ai_clients.openai_client import OpenAIClient

app = FastAPI(title="EDGAR RAG")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

llm = OpenAIClient()


@app.on_event("startup")
def startup():
    init_db()


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    question = body["question"]
    session_id = body.get("session_id")

    if not session_id:
        session = sessions.create_session(question[:80])
        session_id = session["id"]

    sessions.add_message(session_id, "user", question)

    # Run query decomposition and ticker detection
    search_plan = decompose_and_expand(question)
    sub_queries = search_plan.queries
    tickers = search_plan.tickers

    # Pass tickers to retrieval so results are filtered to relevant documents
    chunks = retrieve_multi(
        sub_queries, 
        tickers=tickers if tickers else None
    )
    user_prompt = build_user_prompt(question, chunks)

    history = sessions.get_messages(session_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[:-1]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_prompt})

    async def stream():
        full_response = []
        async for token in llm.generate_stream(messages):
            full_response.append(token)
            yield f"data: {json.dumps({'token': token})}\n\n"

        content = "".join(full_response)
        sessions.add_message(session_id, "assistant", content)

        sources = []
        seen = set()
        for c in chunks:
            key = (c.get("ticker"), c.get("filing_type"), c.get("filing_date"))
            if key not in seen:
                seen.add(key)
                sources.append({
                    "ticker": c.get("ticker"),
                    "filing_type": c.get("filing_type"),
                    "filing_date": c.get("filing_date"),
                    "quarter": c.get("quarter"),
                })

        yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'sources': sources})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/sessions")
async def create_session_route(request: Request):
    body = await request.json()
    session = sessions.create_session(body.get("title", "New Chat"))
    return session


@app.get("/api/sessions")
async def list_all_sessions():
    return sessions.list_sessions()


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: int):
    return sessions.get_messages(session_id)


@app.delete("/api/sessions/{session_id}")
async def delete_session_route(session_id: int):
    sessions.delete_session(session_id)
    return {"ok": True}


app.mount("/", StaticFiles(directory="ui", html=True), name="ui")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)

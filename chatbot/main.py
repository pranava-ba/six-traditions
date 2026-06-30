"""
main.py — FastAPI app.

Endpoints:
  POST /webhook        — WhatsApp webhook (drop-in for Twilio / Meta)
  POST /mock           — Local testing: {session_id, message} → {replies: [...]}
  GET  /flagged        — List unresolvable temples (admin/review)
  GET  /health         — Health check
  GET  /session/{id}   — Inspect session state (dev)
  DELETE /session/{id} — Clear session (dev)
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel

from chatbot import conversation, db, formatter

app = FastAPI(title="Six Traditions Temple Circuit Chatbot", version="1.0.0")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    import sqlite3, pathlib
    db_path = pathlib.Path(__file__).parent.parent / "temples.db"
    with sqlite3.connect(db_path) as con:
        count = con.execute("SELECT COUNT(*) FROM temples").fetchone()[0]
    return {"status": "ok", "temples_in_db": count}


# ── Mock endpoint (local testing) ────────────────────────────────────────────
class MockRequest(BaseModel):
    session_id: str
    message: str

@app.post("/mock")
def mock_chat(req: MockRequest):
    replies = conversation.handle(req.session_id, req.message)
    return {"session_id": req.session_id, "replies": replies}


# ── WhatsApp webhook (Twilio format, adaptable to Meta) ───────────────────────
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    body       = form.get("Body", "").strip()
    session_id = form.get("From", "unknown")   # e.g. "whatsapp:+919XXXXXXXXX"

    if not body:
        return PlainTextResponse("", status_code=200)

    replies = conversation.handle(session_id, body)

    # For Twilio: return TwiML with one message (or the first if many)
    # For Meta Cloud API: you'd call the messages endpoint instead
    twiml_parts = "".join(f"<Message>{r}</Message>" for r in replies)
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>{twiml_parts}</Response>"""
    return PlainTextResponse(twiml, media_type="text/xml")


# ── Admin: flagged temples ────────────────────────────────────────────────────
@app.get("/flagged")
def get_flagged():
    return {"flagged": db.flagged_temples()}


# ── Dev: session inspect / clear ─────────────────────────────────────────────
@app.get("/session/{session_id}")
def get_session(session_id: str):
    state = db.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "state": state}

@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    db.clear_session(session_id)
    return {"deleted": session_id}

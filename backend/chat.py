"""Team chat endpoints."""
from fastapi import APIRouter, Depends

from .auth import verify_token
from .database import connect_db
from .schemas import ChatMessage

router = APIRouter()


@router.post("/chat")
def post_message(data: ChatMessage, username: str = Depends(verify_token)):
    with connect_db() as conn:
        with conn:
            conn.execute(
                "INSERT INTO messages (username, text) VALUES (?, ?)",
                (username, data.text.strip()),
            )
    return {"status": "success"}


@router.get("/chat")
def get_messages(username: str = Depends(verify_token)):
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT username, text, timestamp FROM messages ORDER BY id DESC LIMIT 50"
        ).fetchall()
    messages = [
        {"username": row[0], "text": row[1], "timestamp": row[2]}
        for row in reversed(rows)
    ]
    return {"messages": messages}

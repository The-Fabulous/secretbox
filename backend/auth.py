"""Registration, sign-in, and shared authentication dependency."""
import datetime
import sqlite3

import bcrypt
import jwt
from fastapi import APIRouter, Header, HTTPException

from .config import ALGORITHM, SECRET_KEY
from .database import connect_db
from .schemas import LoginData

router = APIRouter()


def validate_password_length(password: str):
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password must be 72 UTF-8 bytes or fewer")


def verify_token(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        return username
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Срок действия токена истек") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Недействительный токен") from exc


@router.post("/register")
def register(data: LoginData):
    username = data.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty")
    validate_password_length(data.password)
    password_hash = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    try:
        with connect_db() as conn:
            with conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Это имя пользователя уже зарегистрировано") from exc
    return {"status": "success", "detail": "Аккаунт создан"}


@router.post("/login")
def login(data: LoginData):
    username = data.username.strip()
    validate_password_length(data.password)
    with connect_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()

    if not row or not bcrypt.checkpw(data.password.encode("utf-8"), row[0].encode("utf-8")):
        raise HTTPException(status_code=400, detail="Неверное имя пользователя или пароль")

    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)
    token = jwt.encode({"sub": username, "exp": expires_at}, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token}

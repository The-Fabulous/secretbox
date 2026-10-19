import datetime
import glob
import logging
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "objects"
DB_FILE = BASE_DIR / "users.db"
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secretbox-local-key-change-before-deployment")
ALGORITHM = "HS256"
SIZE_RE = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(ml|мл|l|л)\b", re.IGNORECASE)
PRICE_LINE_RE = re.compile(r"^(.+?)\s*[-—–]\s*([\d][\d\s.,]*)\s*(?:₸|KZT)?\s*$", re.IGNORECASE)
logger = logging.getLogger("secretbox")

app = FastAPI(title="SecretBox Cafe Menu API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginData(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ChatMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class MenuItemInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    size_ml: int | None = Field(default=None, gt=0, le=5000)
    price: int = Field(gt=0, le=1_000_000)


class MenuUpdate(BaseModel):
    items: list[MenuItemInput] = Field(min_length=1, max_length=1000)


def validate_password_length(password: str):
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password must be 72 UTF-8 bytes or fewer")


def init_db():
    with closing(sqlite3.connect(DB_FILE)) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    text TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS menu_metadata (
                    shop_name TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL
                )
                """
            )


init_db()


def parse_menu_line(line: str) -> dict | None:
    match = PRICE_LINE_RE.match(line.strip())
    if not match:
        return None

    name = match.group(1).strip()
    price = int(re.sub(r"\D", "", match.group(2)))
    size_match = SIZE_RE.search(name)
    size_ml = None
    if size_match:
        amount = float(size_match.group(1).replace(",", "."))
        unit = size_match.group(2).lower()
        size_ml = round(amount * 1000) if unit in ("l", "л") else round(amount)
        if size_ml <= 0 or size_ml > 5000:
            return None
        name = SIZE_RE.sub("", name).strip(" -—–,()")

    if not name or price <= 0:
        return None

    return {"name": name, "size_ml": size_ml, "price": price, "currency": "₸"}


def read_menu(path: Path) -> list[dict]:
    items = []
    with path.open("r", encoding="utf-8-sig") as menu_file:
        for line_number, line in enumerate(menu_file, start=1):
            if not line.strip():
                continue
            item = parse_menu_line(line)
            if item is None:
                logger.warning("Ignoring unrecognized menu line %s:%s", path.name, line_number)
                continue
            items.append(item)
    return items


def get_shop_path(shop_name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", shop_name):
        raise HTTPException(status_code=404, detail="Кофейня не найдена")
    path = DATA_DIR / f"{shop_name}_menu.txt"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Кофейня не найдена")
    return path


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


@app.post("/register")
def register(data: LoginData):
    username = data.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty")
    validate_password_length(data.password)
    password_hash = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    try:
        with closing(sqlite3.connect(DB_FILE)) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Это имя пользователя уже зарегистрировано") from exc
    return {"status": "success", "detail": "Аккаунт создан"}


@app.post("/login")
def login(data: LoginData):
    username = data.username.strip()
    validate_password_length(data.password)
    with closing(sqlite3.connect(DB_FILE)) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()

    if not row or not bcrypt.checkpw(data.password.encode("utf-8"), row[0].encode("utf-8")):
        raise HTTPException(status_code=400, detail="Неверное имя пользователя или пароль")

    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)
    token = jwt.encode({"sub": username, "exp": expires_at}, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token}


@app.post("/chat")
def post_message(data: ChatMessage, username: str = Depends(verify_token)):
    with closing(sqlite3.connect(DB_FILE)) as conn:
        with conn:
            conn.execute(
                "INSERT INTO messages (username, text) VALUES (?, ?)",
                (username, data.text.strip()),
            )
    return {"status": "success"}


@app.get("/chat")
def get_messages(username: str = Depends(verify_token)):
    with closing(sqlite3.connect(DB_FILE)) as conn:
        rows = conn.execute(
            "SELECT username, text, timestamp FROM messages ORDER BY id DESC LIMIT 50"
        ).fetchall()
    messages = [
        {"username": row[0], "text": row[1], "timestamp": row[2]}
        for row in reversed(rows)
    ]
    return {"messages": messages}


@app.get("/coffee-shops")
def get_shops(username: str = Depends(verify_token)):
    files = glob.glob(str(DATA_DIR / "*_menu.txt"))
    shops = sorted(Path(filename).name.removesuffix("_menu.txt") for filename in files)
    return {"shops": shops}


@app.get("/menu/{shop_name}")
def get_menu(shop_name: str, username: str = Depends(verify_token)):
    path = get_shop_path(shop_name)
    items = read_menu(path)
    legacy_menu = {
        f"{item['name']} ({item['size_ml']} ml)" if item["size_ml"] else item["name"]:
        f"{item['price']} ₸"
        for item in items
    }
    with closing(sqlite3.connect(DB_FILE)) as conn:
        row = conn.execute(
            "SELECT updated_at FROM menu_metadata WHERE shop_name = ?", (shop_name,)
        ).fetchone()
    updated_at = row[0] if row else None
    return {"menu": legacy_menu, "items": items, "updated_at": updated_at}


@app.put("/menu/{shop_name}")
def update_menu(shop_name: str, data: MenuUpdate, username: str = Depends(verify_token)):
    path = get_shop_path(shop_name)
    lines = []
    for item in data.items:
        name = item.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Название напитка не может быть пустым")
        size = f" {item.size_ml} ml" if item.size_ml is not None else ""
        lines.append(f"{name}{size} — {item.price} ₸")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with closing(sqlite3.connect(DB_FILE)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO menu_metadata (shop_name, updated_at) VALUES (?, ?)
                ON CONFLICT(shop_name) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (shop_name, updated_at),
            )
    return {"status": "success", "items": len(lines)}


def normalize_name(name: str) -> str:
    return "".join(character.casefold() for character in name if character.isalnum())


@app.get("/analytics/compare")
def compare_prices(username: str = Depends(verify_token)):
    grouped: dict[tuple[str, int | None], dict] = {}
    for filename in glob.glob(str(DATA_DIR / "*_menu.txt")):
        shop_name = Path(filename).name.removesuffix("_menu.txt")
        for item in read_menu(Path(filename)):
            key = (normalize_name(item["name"]), item["size_ml"])
            row = grouped.setdefault(
                key,
                {
                    "Напиток": item["name"],
                    "Объём": f"{item['size_ml']} мл" if item["size_ml"] else "Не указан",
                    "prices": {},
                    "numeric_prices": [],
                },
            )
            row["prices"][shop_name] = f"{item['price']} ₸"
            row["numeric_prices"].append(item["price"])

    results = []
    for row in grouped.values():
        if len(row["prices"]) < 2:
            continue
        result = {"Напиток": row["Напиток"], "Объём": row["Объём"]}
        result.update(row["prices"])
        result["Разброс"] = max(row["numeric_prices"]) - min(row["numeric_prices"])
        results.append(result)
    return results

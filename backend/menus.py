"""Cafe menus, persistence, and text imports."""
import datetime
import glob
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import verify_token
from .config import DATA_DIR
from .database import connect_db
from .menu_parser import parse_menu_import
from .menu_storage import read_menu, write_menu
from .schemas import MenuUpdate

router = APIRouter()


def get_shop_path(shop_name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", shop_name):
        raise HTTPException(status_code=404, detail="Кофейня не найдена")
    path = DATA_DIR / f"{shop_name}_menu.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Кофейня не найдена")
    return path


@router.get("/coffee-shops")
def get_shops(username: str = Depends(verify_token)):
    files = glob.glob(str(DATA_DIR / "*_menu.json"))
    shops = sorted(Path(filename).name.removesuffix("_menu.json") for filename in files)
    return {"shops": shops}


@router.get("/menu/{shop_name}")
def get_menu(shop_name: str, username: str = Depends(verify_token)):
    path = get_shop_path(shop_name)
    items = read_menu(path)
    legacy_menu = {
        f"{item['name']} ({item['size_ml']} ml)" if item["size_ml"] else item["name"]:
        f"{item['price']} ₸"
        for item in items
    }
    with connect_db() as conn:
        row = conn.execute(
            "SELECT updated_at FROM menu_metadata WHERE shop_name = ?", (shop_name,)
        ).fetchone()
    updated_at = row[0] if row else None
    return {"menu": legacy_menu, "items": items, "updated_at": updated_at}


@router.put("/menu/{shop_name}")
def update_menu(shop_name: str, data: MenuUpdate, username: str = Depends(verify_token)):
    path = get_shop_path(shop_name)
    write_menu(path, data)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with connect_db() as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO menu_metadata (shop_name, updated_at) VALUES (?, ?)
                ON CONFLICT(shop_name) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (shop_name, updated_at),
            )
    return {"status": "success", "items": len(data.items)}


@router.put("/api/menus/{shop_name}")
async def import_menu(shop_name: str, request: Request, username: str = Depends(verify_token)):
    get_shop_path(shop_name)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 2_000_000:
            raise HTTPException(status_code=413, detail="Menu file is too large (2 MB maximum)")
        body.extend(chunk)
    try:
        content = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Menu file must use UTF-8 encoding") from exc
    return update_menu(shop_name, parse_menu_import(content), username)

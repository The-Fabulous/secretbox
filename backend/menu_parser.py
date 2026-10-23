"""Menu text parsing shared by imports and price comparisons."""
import re

from fastapi import HTTPException
from pydantic import ValidationError

from .schemas import MenuDocument, MenuItemInput, MenuUpdate

SIZE_RE = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(ml|мл|l|л)\b", re.IGNORECASE)
PRICE_LINE_RE = re.compile(r"^(.+?)\s*[-—–]\s*([\d][\d\s.,]*)\s*(?:₸|KZT)?\s*$", re.IGNORECASE)


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

    return {"name": name, "size_ml": size_ml, "price": price}


def parse_menu_import(content: str) -> MenuUpdate:
    content = content.lstrip("\ufeff").strip()
    if content.startswith(("{", "[")):
        try:
            return MenuDocument.model_validate_json(content)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail="Invalid menu JSON: use an items array with name, size_ml and price; currency must be KZT") from exc
    items = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        line = line.strip().lstrip("\ufeff").strip()
        if not line:
            continue
        try:
            if "|" in line:
                name, size, price = (part.strip() for part in line.split("|"))
                size_ml = None
                if size:
                    match = SIZE_RE.fullmatch(size)
                    if not match:
                        raise ValueError("Size must include ml or l")
                    amount = float(match.group(1).replace(",", "."))
                    size_ml = round(amount * 1000) if match.group(2).lower() in ("l", "л") else round(amount)
                if not re.fullmatch(r"[\d][\d\s.,]*(?:₸|KZT)?", price, re.IGNORECASE):
                    raise ValueError("Invalid price")
                item = {"name": name, "size_ml": size_ml, "price": int(re.sub(r"\D", "", price))}
            else:
                item = parse_menu_line(line)
                if item is None:
                    raise ValueError("Invalid menu format")
            items.append(MenuItemInput(**item))
            if len(items) > 1000:
                raise ValueError("Maximum 1000 drinks")
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Could not read menu line {line_number}") from exc
    try:
        return MenuUpdate(items=items)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="The menu must contain at least one drink") from exc

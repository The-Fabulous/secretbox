"""Compare matching drinks across cafe menus."""
import glob
from pathlib import Path

from fastapi import APIRouter, Depends

from .auth import verify_token
from .config import DATA_DIR
from .menu_storage import read_menu

router = APIRouter()


def normalize_name(name: str) -> str:
    return "".join(character.casefold() for character in name if character.isalnum())


@router.get("/analytics/compare")
def compare_prices(username: str = Depends(verify_token)):
    grouped: dict[tuple[str, int | None], dict] = {}
    for filename in glob.glob(str(DATA_DIR / "*_menu.json")):
        shop_name = Path(filename).name.removesuffix("_menu.json")
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

"""Validated JSON menu storage with atomic file replacement."""
import os
import tempfile
from pathlib import Path

from .schemas import MenuDocument, MenuUpdate


def read_document(path: Path) -> MenuDocument:
    return MenuDocument.model_validate_json(path.read_text(encoding="utf-8-sig"))


def read_menu(path: Path) -> list[dict]:
    # Preserve the public API's currency symbol while storing ISO currency in JSON.
    return [dict(item.model_dump(), currency="₸") for item in read_document(path).items]


def write_menu(path: Path, menu: MenuUpdate) -> None:
    document = MenuDocument(items=menu.items)
    content = document.model_dump_json(indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

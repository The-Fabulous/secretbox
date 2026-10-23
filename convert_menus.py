"""Convert legacy *_menu.txt files to validated JSON without overwriting menus."""
import argparse
from pathlib import Path

from backend.config import DATA_DIR
from backend.menu_parser import parse_menu_import
from backend.menu_storage import read_document, write_menu
from backend.schemas import MenuDocument


def convert_menus(directory: Path, remove_source: bool = False) -> list[tuple[str, int]]:
    directory = directory.resolve(strict=True)
    planned = []
    # Validate every source and existing destination before changing any files.
    for source in sorted(directory.glob("*_menu.txt")):
        destination = source.with_suffix(".json")
        if source.is_symlink() or destination.is_symlink():
            raise ValueError(f"Refusing symlink: {source.name}")
        menu = MenuDocument(items=parse_menu_import(source.read_text(encoding="utf-8-sig")).items)
        if destination.exists() and read_document(destination) != menu:
            raise ValueError(f"{destination.name} differs from source; refusing to overwrite")
        planned.append((source, destination, menu))
    for source, destination, menu in planned:
        if not destination.exists():
            write_menu(destination, menu)
        if read_document(destination) != menu:
            raise ValueError(f"Verification failed: {destination.name}")
        if remove_source:
            source.unlink()
    return [(destination.name, len(menu.items)) for _, destination, menu in planned]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DATA_DIR)
    parser.add_argument("--remove-source", action="store_true", help="Remove TXT only after verifying the JSON")
    args = parser.parse_args()
    for name, count in convert_menus(args.directory, args.remove_source):
        print(f"{name}: {count} items")


if __name__ == "__main__":
    main()

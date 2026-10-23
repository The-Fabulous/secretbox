"""Migration and storage regression checks using temporary menu files."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.menu_storage import read_document, write_menu
from backend.schemas import MenuDocument, MenuItemInput
from convert_menus import convert_menus


class MenuConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "Cafe_menu.txt"
        self.source.write_text("\ufeffЛатте 350 ml — 1190 ₸\nЧай — 590 ₸\n", encoding="utf-8")
        self.target = self.source.with_suffix(".json")

    def test_conversion_and_verified_source_removal(self):
        self.assertEqual(convert_menus(self.root), [("Cafe_menu.json", 2)])
        self.assertTrue(self.source.exists())
        menu = read_document(self.target)
        self.assertEqual(menu.currency, "KZT")
        self.assertEqual([item.name for item in menu.items], ["Латте", "Чай"])
        self.assertEqual([item.size_ml for item in menu.items], [350, None])
        self.assertEqual([item.price for item in menu.items], [1190, 590])
        convert_menus(self.root, remove_source=True)
        self.assertFalse(self.source.exists())
        self.assertEqual(read_document(self.target), menu)
        self.assertEqual(convert_menus(self.root), [])

    def test_invalid_source_changes_no_files(self):
        (self.root / "Other_menu.txt").write_text("unrecognized line", encoding="utf-8")
        with self.assertRaises(HTTPException):
            convert_menus(self.root, remove_source=True)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.target.exists())

    def test_existing_different_json_is_preserved(self):
        write_menu(self.target, MenuDocument(items=[MenuItemInput(name="Tea", price=100)]))
        previous = self.target.read_bytes()
        with self.assertRaises(ValueError):
            convert_menus(self.root, remove_source=True)
        self.assertEqual(self.target.read_bytes(), previous)
        self.assertTrue(self.source.exists())

    def test_failed_replacement_keeps_previous_menu(self):
        convert_menus(self.root)
        previous = self.target.read_bytes()
        with patch("backend.menu_storage.os.replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                write_menu(self.target, MenuDocument(items=[MenuItemInput(name="Tea", price=100)]))
        self.assertEqual(self.target.read_bytes(), previous)
        self.assertFalse(list(self.root.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()

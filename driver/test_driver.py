import argparse
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from driver import driver


class SecretBoxMenuTests(unittest.TestCase):
    def test_expands_sizes_to_secretbox_lines(self):
        items = driver.secretbox_items({
            'items': [{
                'name': 'КАПУЧИНО',
                'variants': [
                    {'measure': '250 мл', 'price': '1 190 ₸'},
                    {'measure': '0.35 л', 'price': 1390},
                ],
            }, {
                'name': 'Какао',
                'measure': None,
                'price': 950,
            }],
        })

        self.assertEqual(items, [
            {'name': 'Капучино', 'size_ml': 250, 'price': 1190},
            {'name': 'Капучино', 'size_ml': 350, 'price': 1390},
            {'name': 'Какао', 'size_ml': None, 'price': 950},
        ])
        self.assertEqual(driver.secretbox_line(items[0]), 'Капучино | 250 ml | 1190')

    def test_non_volume_measure_is_kept_in_display_name(self):
        items = driver.secretbox_items({
            'items': [{'name': 'Круассан', 'measure': '80 г', 'price': 650}],
        })

        self.assertEqual(items[0], {'name': 'Круассан (80 г)', 'size_ml': None, 'price': 650})

    def test_numeric_size_is_treated_as_millilitres(self):
        items = driver.secretbox_items({
            'items': [{'name': 'Латте', 'size_ml': 350, 'price': 1200}],
        })

        self.assertEqual(items[0], {'name': 'Латте', 'size_ml': 350, 'price': 1200})

    def test_size_in_name_is_extracted(self):
        items = driver.secretbox_items({
            'items': [{'name': 'Латте 350 мл', 'price': 1200}],
        })

        self.assertEqual(items[0], {'name': 'Латте', 'size_ml': 350, 'price': 1200})

    def test_conflicting_duplicate_prices_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'разные цены'):
            driver.secretbox_items({
                'items': [
                    {'name': 'Латте', 'measure': '250 ml', 'price': 1000},
                    {'name': 'Латте', 'measure': '250 ml', 'price': 1100},
                ],
            })

    def test_merge_updates_matches_and_preserves_other_items(self):
        existing = [
            {'name': 'Латте', 'size_ml': 250, 'price': 1000},
            {'name': 'Какао', 'size_ml': None, 'price': 900},
        ]
        recognized = [
            {'name': 'Латте', 'size_ml': 250, 'price': 1100},
            {'name': 'Матча', 'size_ml': 350, 'price': 1300},
        ]

        merged, updated, added = driver.merge_secretbox_menu(existing, recognized)

        self.assertEqual(merged, [
            {'name': 'Латте', 'size_ml': 250, 'price': 1100},
            {'name': 'Какао', 'size_ml': None, 'price': 900},
            {'name': 'Матча', 'size_ml': 350, 'price': 1300},
        ])
        self.assertEqual((updated, added), (1, 1))

    def test_merge_deduplicates_same_price_and_rejects_conflicting_prices(self):
        item = {'name': 'Латте', 'size_ml': 250, 'price': 1100}
        merged, updated, added = driver.merge_secretbox_menu([], [item, item.copy()])
        self.assertEqual(merged, [item])
        self.assertEqual((updated, added), (0, 1))

        with self.assertRaisesRegex(ValueError, 'разные цены'):
            driver.merge_secretbox_menu([], [
                item,
                {'name': 'Латте', 'size_ml': 250, 'price': 1200},
            ])

    def test_existing_text_menu_is_parsed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'menu.txt'
            path.write_text('Латте 250 мл — 1 190 ₸\nКакао — 950₸\n', encoding='utf-8')

            items = driver.read_secretbox_menu(path)

        self.assertEqual(items, [
            {'name': 'Латте', 'size_ml': 250, 'price': 1190},
            {'name': 'Какао', 'size_ml': None, 'price': 950},
        ])

    def test_run_merge_writes_draft_without_changing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            objects = root / 'objects'
            objects.mkdir()
            source = objects / 'Cafe_menu.txt'
            original = 'Латте 250 мл — 1000 ₸\nКакао — 900 ₸\n'
            source.write_text(original, encoding='utf-8')
            screenshot = root / 'menu.png'
            screenshot.write_bytes(b'image')
            draft = root / 'draft.txt'
            openai_stub = types.ModuleType('openai')
            openai_stub.OpenAI = Mock(return_value=object())
            args = argparse.Namespace(
                secretbox_shop='Cafe', menu_mode='merge', cafe_id=None, out=None,
                from_cache=False, publish=False, photos_from_menu=True,
                max_width=1600, draft_out=str(draft),
            )

            with patch.object(driver, 'SECRETBOX_OBJECTS', objects), \
                    patch.object(driver, 'image_tiles', return_value=[(None, 'data')]), \
                    patch.object(driver, 'ask_secretbox_menu', return_value=[
                        {'name': 'Латте', 'size_ml': 250, 'price': 1100},
                        {'name': 'Матча', 'size_ml': None, 'price': 1300},
                    ]), \
                    patch.dict(sys.modules, {'openai': openai_stub}):
                driver.run_secretbox_mode(
                    args, argparse.ArgumentParser(), screenshot, 'test-key', 'https://example.test', 'test-model',
                )

            self.assertEqual(source.read_text(encoding='utf-8'), original)
            self.assertEqual(draft.read_text(encoding='utf-8'), (
                'Латте | 250 ml | 1100\nКакао |  | 900\nМатча |  | 1300\n'
            ))


if __name__ == '__main__':
    unittest.main()

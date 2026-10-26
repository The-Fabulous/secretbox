import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readdirSync, readFileSync } from 'node:fs';
import { compareMenus } from '../src/utils/compareMenus.js';
import { authErrorMessage } from '../src/utils/errors.js';

test('guest comparison matches names and volumes across distinct cafes', () => {
  const rows = compareMenus({
    First: { items: [
      { name: 'Латте!', size_ml: 350, price: 1190 },
      { name: 'Tea', size_ml: null, price: 590 },
      { name: 'Only here', price: 100 },
    ] },
    Second: { items: [
      { name: 'латте', size_ml: 350, price: 1390 },
      { name: 'Латте', size_ml: 250, price: 990 },
      { name: 'Tea', price: 790 },
    ] },
  });
  assert.equal(rows.length, 2);
  assert.deepEqual(rows[0], {
    'Напиток': 'Латте!', 'Объём': '350 мл', First: '1190 ₸', Second: '1390 ₸', 'Разброс': 200,
  });
  assert.equal(rows[1]['Объём'], 'Не указан');
  assert.equal(rows[1]['Разброс'], 200);
});

test('duplicate drinks in one cafe are not counted as multiple cafes', () => {
  assert.deepEqual(compareMenus({ Only: { items: [
    { name: 'Tea', price: 590 }, { name: 'Tea', price: 790 },
  ] } }), []);
});

test('bundled menus provide real catalog and comparison data', () => {
  const directory = new URL('../../objects/', import.meta.url);
  const files = readdirSync(directory).filter((name) => name.endsWith('_menu.json'));
  assert.ok(files.length >= 2);
  const menus = Object.fromEntries(files.map((name) => [
    name.replace(/_menu\.json$/, ''), JSON.parse(readFileSync(new URL(name, directory), 'utf8')),
  ]));
  for (const menu of Object.values(menus)) {
    assert.ok(menu.items.length > 0);
    assert.ok(menu.items.every((item) => item.name && item.price > 0));
  }
  assert.ok(compareMenus(menus).length > 0);
});

test('validation and connection errors produce renderable text', () => {
  assert.equal(authErrorMessage({ response: { data: { detail: [{ msg: 'Too long' }] } } }), 'Too long');
  assert.equal(authErrorMessage({ response: { data: { detail: 'Wrong password' } } }), 'Wrong password');
  assert.match(authErrorMessage({}), /continue as guest/);
  assert.equal(typeof authErrorMessage({ response: { data: { detail: [{ msg: {} }] } } }), 'string');
});

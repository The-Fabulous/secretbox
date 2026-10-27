"""Распознаёт фото меню через Gemma и собирает целую вкладку в tabs/<id>/.

Папка результата: cafe.json, menu.json, images/, logo.*, raw/ (ответы для проверки).
Каждое фото отправляется в модель отдельно, позиции со всех фото объединяются в одно меню,
а ответ модели проверяется и приводится к формату сайта: цены — числами, неизвестное — null,
id — латиницей, пути к фото — images/<id>.jpg относительно menu.json.

Запуск:
  python driver.py ../venues/ayu_menu
  python driver.py ../venues/ayu_menu --out output/tabs/ayu_menu
  python driver.py ../menu-screenshots --secretbox-shop Ayu --menu-mode replace

Ключ API — в файле .env рядом со скриптом (OPENAI_API_KEY=...).
"""

import argparse
import base64
import io
import json
import mimetypes
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / 'coffee-menu'
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
SECRETBOX_OBJECTS = HERE.parent / 'objects'
SECRETBOX_PRICE_LINE_RE = re.compile(r'^(.+?)\s*[-—–]\s*([\d][\d\s.,]*)\s*(?:₸|KZT)?\s*$', re.I)
SECRETBOX_SIZE_RE = re.compile(r'(?<!\d)(\d+(?:[.,]\d+)?)\s*(ml|мл|l|л)(?!\w)', re.I)

SECRETBOX_PROMPT = """На изображениях — меню кофейни. Перепиши все видимые позиции и цены.
Ответь только JSON такого вида:
{"items":[{"name":"Американо","measure":"250 мл","price":890}]}
Правила:
- Одна строка на каждый размер и цену; не объединяй несколько размеров в одну позицию.
- Если объём не указан, укажи measure: null. Не выдумывай объём, название или цену.
- Переписывай название точно как на изображении, цену указывай числом без валюты и разделителей тысяч.
- Не добавляй заголовки разделов, описания и рекламный текст как позиции.
- Если значение не удаётся прочитать уверенно, не угадывай: остановись с JSON {"items":[]}."""


def _secretbox_key(name, size_ml):
    normalized = ''.join(ch for ch in name.casefold().replace('ё', 'е') if ch.isalnum())
    return normalized, size_ml


def _secretbox_size(measure):
    """Возвращает миллилитры для поддерживаемых приложением ml/l, иначе None."""
    match = SECRETBOX_SIZE_RE.search(measure or '')
    if not match:
        return None
    amount = float(match.group(1).replace(',', '.'))
    unit = match.group(2).lower()
    size_ml = round(amount * 1000) if unit in ('l', 'л') else round(amount)
    if size_ml <= 0 or size_ml > 5000:
        raise ValueError(f'Некорректный объём: {measure}')
    return size_ml


def secretbox_items(data):
    """Приводит JSON модели к уникальным (название, мл, цена) для меню SecretBox."""
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('Ответ модели не содержит список items')

    items = {}
    for raw in data['items']:
        if not isinstance(raw, dict):
            raise ValueError('В ответе меню найдена позиция неверного формата')
        name = tidy_name(raw.get('name'))
        if not name:
            raise ValueError('В ответе меню найдена позиция без названия')

        variants = raw.get('variants')
        if not isinstance(variants, list) or not variants:
            variants = [raw]
        for variant in variants:
            if not isinstance(variant, dict):
                raise ValueError(f'Неверный формат варианта у «{name}»')
            price = to_price(variant.get('price'))
            if price is None:
                raise ValueError(f'Не распознана цена у «{name}»; черновик не создан')

            measure_value = (
                variant.get('measure') or variant.get('size') or variant.get('size_ml')
                or raw.get('measure') or raw.get('size') or raw.get('size_ml')
            )
            measure = str(measure_value).strip() if isinstance(measure_value, (str, int, float)) else None
            if measure and measure.replace('.', '', 1).replace(',', '', 1).isdigit():
                measure = f'{measure} ml'
            size_ml = _secretbox_size(measure) if measure else None
            display_name = name
            if measure and size_ml is None:
                display_name = f'{name} ({measure})'
            elif not measure:
                name_size = SECRETBOX_SIZE_RE.search(name)
                if name_size:
                    size_ml = _secretbox_size(name_size.group(0))
                    display_name = SECRETBOX_SIZE_RE.sub('', name).strip(' -—–,()')

            key = _secretbox_key(display_name, size_ml)
            item = {'name': display_name, 'size_ml': size_ml, 'price': price}
            existing = items.get(key)
            if existing and existing['price'] != price:
                raise ValueError(
                    f'Для «{display_name}» распознаны разные цены ({existing["price"]} и {price}); '
                    'проверьте скриншоты'
                )
            items[key] = item
    return list(items.values())


def secretbox_line(item):
    size = f'{item["size_ml"]} ml' if item['size_ml'] else ''
    return f'{item["name"]} | {size} | {item["price"]}'


def read_secretbox_menu(path):
    """Читает исходное текстовое меню; неразбираемые строки нельзя безопасно объединять."""
    items = []
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        match = SECRETBOX_PRICE_LINE_RE.match(line.strip())
        if not match:
            raise ValueError(f'Не удалось прочитать строку {number} в текущем меню: {line}')
        name = match.group(1).strip()
        price = to_price(match.group(2))
        size_match = SECRETBOX_SIZE_RE.search(name)
        size_ml = _secretbox_size(size_match.group(0)) if size_match else None
        if size_match:
            name = SECRETBOX_SIZE_RE.sub('', name).strip(' -—–,()')
        if not name or price is None:
            raise ValueError(f'Некорректная строка {number} в текущем меню')
        items.append({'name': name, 'size_ml': size_ml, 'price': price})
    return items


def merge_secretbox_menu(existing, recognized):
    """Обновляет совпавшие название+объём, оставляет остальные позиции и добавляет новые."""
    merged = list(existing)
    indexes = {}
    seen_recognized = {}
    for index, item in enumerate(merged):
        key = _secretbox_key(item['name'], item['size_ml'])
        if key in indexes and merged[indexes[key]]['price'] != item['price']:
            raise ValueError(f'В текущем меню неоднозначные дубликаты: «{item["name"]}»')
        indexes.setdefault(key, index)

    updated = 0
    added = 0
    for item in recognized:
        key = _secretbox_key(item['name'], item['size_ml'])
        if key in seen_recognized and seen_recognized[key] != item['price']:
            raise ValueError(
                f'На скриншотах для «{item["name"]}» распознаны разные цены '
                f'({seen_recognized[key]} и {item["price"]}); проверьте скриншоты'
            )
        seen_recognized[key] = item['price']
        if key in indexes:
            index = indexes[key]
            if merged[index]['price'] != item['price']:
                merged[index] = item
                updated += 1
        else:
            indexes[key] = len(merged)
            merged.append(item)
            added += 1
    return merged, updated, added


def ask_secretbox_menu(client, model, data_url):
    data, _ = call_model(client, model, [
        {'role': 'system', 'content': 'Ты точно переписываешь названия и цены меню с изображений. Отвечаешь только JSON.'},
        {'role': 'user', 'content': [
            {'type': 'text', 'text': SECRETBOX_PROMPT},
            {'type': 'image_url', 'image_url': {'url': data_url}},
        ]},
    ], max_tokens=8192)
    return secretbox_items(data)

# ───────── настройки

def load_env(path):
    """Простой разбор .env: KEY=VALUE, # — комментарий. Переменные окружения важнее файла."""
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError):
        return fallback


# ───────── фото → фрагменты для модели
#
# Длинный скриншот меню (например, 1268×21000) нельзя просто уменьшить: текст станет нечитаемым.
# Поэтому ширина ограничивается max_width, а по высоте картинка режется на фрагменты с перекрытием,
# чтобы карточка, разрезанная краем одного фрагмента, целиком попала в соседний.

TILE_HEIGHT = 2000
TILE_OVERLAP = 700


def to_data_url(im):
    buf = io.BytesIO()
    im.convert('RGB').save(buf, 'JPEG', quality=90)
    return f'data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}'


def image_tiles(path, max_width):
    """Фрагменты фото сверху вниз: [(картинка PIL или None, data URL)]. Картинка нужна, чтобы вырезать фото позиций."""
    try:
        from PIL import Image, ImageOps
    except ImportError:  # без Pillow отправляем как есть, без вырезания фото
        mime = mimetypes.guess_type(path.name)[0] or 'image/jpeg'
        return [(None, f'data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}')]

    im = ImageOps.exif_transpose(Image.open(path)).convert('RGB')  # фото с телефона бывают повёрнуты
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    w, h = im.size
    tile_h = max(TILE_HEIGHT, round(w * 1.2))
    if h <= tile_h * 1.15:
        return [(im, to_data_url(im))]

    step = tile_h - TILE_OVERLAP
    tops = list(range(0, h - tile_h, step)) + [h - tile_h]  # последний фрагмент — ровно до низа
    return [(t, to_data_url(t)) for t in (im.crop((0, top, w, top + tile_h)) for top in tops)]


# ───────── фото позиций: модель указывает, где фото, скрипт уточняет рамку и вырезает

PHOTO_PROMPT = """На изображении — меню кофейни. Найди фотографии позиций (фото напитка или блюда).
Не считай фотографией: значок загрузки, пустую или тёмную карточку, иконки, кнопки, логотип, фон,
а также бледное (полупрозрачное) фото с надписью поверх — «Скоро», «Нет в наличии», «Закончилось».
Если название позиции под фото не видно целиком (обрезано краем изображения) — пропусти это фото,
не угадывай название.
Для каждой фотографии укажи название позиции, к которой она относится (как написано на карточке),
и рамку самой фотографии в координатах 0..1000 относительно ширины и высоты изображения: [x1, y1, x2, y2],
где (x1, y1) — левый верхний угол, (x2, y2) — правый нижний; x — по горизонтали, y — по вертикали.
Ответ — только JSON: {"photos": [{"name": "...", "box": [x1, y1, x2, y2]}]}. Если фотографий нет — {"photos": []}."""


def ask_photos(client, model, data_url):
    """Где на фрагменте фото позиций. Ошибка здесь не мешает меню — просто будут эмодзи."""
    try:
        data, _ = call_model(client, model, [{'role': 'user', 'content': [
            {'type': 'text', 'text': PHOTO_PROMPT},
            {'type': 'image_url', 'image_url': {'url': data_url}},
        ]}], max_tokens=3000)
        photos = data.get('photos') or [] if isinstance(data, dict) else []
        return [p for p in photos if isinstance(p, dict) and text_or_null(p.get('name'))
                and isinstance(p.get('box'), list) and len(p['box']) == 4]
    except Exception as e:
        print(f'    (фото позиций не найдены — будут эмодзи: {str(e)[:150]})')
        return []


CARD_SIZE = 600      # фото позиции на сайте — квадрат CARD_SIZE×CARD_SIZE
CARD_MARGIN = 0.08   # поле вокруг предмета, доля стороны
MAX_UPSCALE = 2.0    # во сколько раз можно увеличить фото со скриншота: сильнее — мыло
CARD_BG = (248, 247, 245)  # общий тон светлого фона плашек


def _content_mask(region):
    """«Не фон»: отличие от цвета фона ИЛИ резкий перепад яркости (контур).
    По контуру видны и предметы цвета фона — белая пачка кофе на белом фоне."""
    import numpy as np
    border = np.concatenate([region[0], region[-1], region[:, 0], region[:, -1]])
    bg = np.median(border, axis=0)
    color = np.abs(region - bg).max(axis=2) > 28
    gray = region.mean(axis=2)
    edges = np.zeros(gray.shape, dtype=bool)
    edges[:, 1:] |= np.abs(np.diff(gray, axis=1)) > 24
    edges[1:, :] |= np.abs(np.diff(gray, axis=0)) > 24
    return color | edges


def is_faded(img):
    """Бледная заглушка «Скоро» / «Нет в наличии» (полупрозрачное фото с надписью поверх).
    Признаки: почти нет средних тонов; либо их мало, а сам предмет очень светлый и выцветший.
    Светлая чашка с какао или белая пачка кофе сюда не попадают: у них есть насыщенные цвета или средние тона."""
    import numpy as np
    a = np.asarray(img.convert('RGB'), dtype=float)
    lum = a.mean(axis=2)
    obj = lum < 235
    if not obj.any():
        return True
    mid = ((lum > 60) & (lum < 200)).mean()
    sat = (a.max(axis=2) - a.min(axis=2)) / (a.max(axis=2) + 1)
    return mid < 0.06 or (mid < 0.13 and lum[obj].mean() > 195 and sat[obj].mean() < 0.12)


def to_card(img, box, center):
    """Квадратная плашка CARD_SIZE×CARD_SIZE из настоящего куска фото — без вырезания по контуру,
    поэтому белая кружка на белом фоне остаётся целой, с родными тенями и бликами.
    img — фото с запасом фона вокруг предмета, box — рамка предмета в нём, center — центр корпуса
    по горизонтали (без ручки кружки): по нему предмет ставится в центр плашки.
    Остальная часть квадрата — фон фото, к краям куска он переходит плавно, а предмета переход не касается.
    Светлый фон всех плашек приводится к одному тону — кремовый, серый и белый не скачут от позиции к позиции."""
    import numpy as np
    from PIL import Image
    a = np.asarray(img.convert('RGB'), dtype=np.float32)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    if bg.min() > 180:  # светлый фон — выравниваем к общему тону
        a = np.clip(a * (CARD_BG / bg), 0, 255)
        bg = np.array(CARD_BG, dtype=np.float32)

    x0, y0, x1, y1 = box
    half = max(center - x0, x1 - center)  # от центра корпуса до дальнего края (ручки)
    inner = CARD_SIZE * (1 - 2 * CARD_MARGIN)
    scale = min(inner / max(2 * half, y1 - y0), MAX_UPSCALE)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    fitted = np.asarray(Image.fromarray(a.astype(np.uint8)).resize(size, Image.LANCZOS), dtype=np.float32)
    left = round(CARD_SIZE / 2 - center * scale)
    top = round(CARD_SIZE / 2 - (y0 + y1) / 2 * scale)

    # короткий переход края куска в продолжение фона (несколько пикселей, только по полю фона, не по предмету)
    def ramp(n, before, after):
        before, after = max(1.0, min(before * scale * 0.8, 8)), max(1.0, min(after * scale * 0.8, 8))
        i = np.arange(n, dtype=np.float32)
        return np.clip(np.minimum((i + 1) / before, (n - i) / after), 0, 1)
    alpha = np.minimum.outer(ramp(size[1], y0, img.height - y1), ramp(size[0], x0, img.width - x1))[..., None]

    # фон за краем куска — продолжение его же краёв (размытое), которое к краям плашки
    # плавно переходит в общий тон: шва нет, даже если фон исходного фото неровный
    from scipy import ndimage
    cx0, cy0 = max(0, -left), max(0, -top)                      # видимая в квадрате часть куска
    cx1, cy1 = min(size[0], CARD_SIZE - left), min(size[1], CARD_SIZE - top)
    piece = fitted[cy0:cy1, cx0:cx1]
    px0, py0 = left + cx0, top + cy0
    pads = ((py0, CARD_SIZE - py0 - piece.shape[0]), (px0, CARD_SIZE - px0 - piece.shape[1]), (0, 0))
    around = np.pad(piece, pads, mode='edge')
    # где предмет упирается в край куска (фона почти нет), продолжать край нельзя — потянется сам предмет
    ph, pw = piece.shape[:2]
    if (y0 - cy0 / scale) * scale < 6: around[:py0] = bg
    if (img.height - y1) * scale - (size[1] - cy1) < 6: around[py0 + ph:] = bg
    if (x0 - cx0 / scale) * scale < 6: around[:, :px0] = bg
    if (img.width - x1) * scale - (size[0] - cx1) < 6: around[:, px0 + pw:] = bg
    around = ndimage.gaussian_filter(around, sigma=(18, 18, 0))
    yy, xx = np.mgrid[0:CARD_SIZE, 0:CARD_SIZE]
    dx = np.maximum(0, np.maximum(px0 - xx, xx - (px0 + piece.shape[1] - 1)))
    dy = np.maximum(0, np.maximum(py0 - yy, yy - (py0 + piece.shape[0] - 1)))
    to_bg = np.clip(np.hypot(dx, dy) / 90, 0, 1)[..., None]
    card = around * (1 - to_bg) + bg * to_bg
    dst = card[py0:py0 + piece.shape[0], px0:px0 + piece.shape[1]]
    al = alpha[cy0:cy1, cx0:cx1]
    dst[:] = piece * al + dst * (1 - al)
    return Image.fromarray(np.clip(card, 0, 255).astype(np.uint8))


def crop_photo(tile, box):
    """Вырезает фото позиции по примерной рамке модели и возвращает квадратную плашку для сайта.
    None — если фото не нашлось (пустая карточка, значок загрузки), это бледная заглушка «Скоро»
    или фото обрезано краем фрагмента. Тогда у позиции будет эмодзи."""
    found = None
    for candidate in _box_orders(box):
        found = _locate_photo(tile, candidate)
        if found is not None:
            break
    if found is None:
        return None
    img, box, center = found
    if is_faded(img.crop(box)):
        return None
    return to_card(img, box, center)


def _box_orders(box):
    """Рамка в порядке [x1, y1, x2, y2], а если в нём она невозможна (правый край левее левого) —
    другие порядки, которые встречаются у моделей: [x1, y1, y2, x2] и [y1, x1, y2, x2]."""
    try:
        a, b, c, d = (float(v) for v in box)
    except (TypeError, ValueError):
        return []
    orders = [(a, b, c, d), (a, b, d, c), (b, a, d, c)]
    return [o for o in orders if o[2] > o[0] and o[3] > o[1]]


def _locate_photo(tile, box):
    """Находит предмет целиком: пиксели, отличные от фона (по цвету или контуру), склеиваются
    в связные фигуры — кружка вместе с ручкой и блюдцем, пачка вместе с надписями. Берутся фигуры,
    которые в основном лежат внутри рамки модели: соседние карточки и подпись снизу отсеиваются.
    Возвращает (фото предмета, маска предмета) или None."""
    import numpy as np
    from scipy import ndimage
    W, H = tile.size
    try:
        x1, y1, x2, y2 = (min(1000.0, max(0.0, float(v))) for v in box)
    except (TypeError, ValueError):
        return None
    if x2 - x1 < 20 or y2 - y1 < 20:
        return None
    bx1, by1, bx2, by2 = x1 * W / 1000, y1 * H / 1000, x2 * W / 1000, y2 * H / 1000
    bw, bh = bx2 - bx1, by2 - by1

    # рамка модели бывает тесной: если предмет упёрся в край области — расширяем и ищем снова
    for expand in (0.35, 0.8):
        ex1, ey1 = int(max(0, bx1 - expand * bw)), int(max(0, by1 - expand * bh))
        ex2, ey2 = int(min(W, bx2 + expand * bw)), int(min(H, by2 + expand * bh))
        region = np.asarray(tile.crop((ex1, ey1, ex2, ey2)), dtype=np.int16)
        if region.shape[0] < 60 or region.shape[1] < 60:
            return None

        mask = _content_mask(region)
        labels, count = ndimage.label(ndimage.binary_dilation(mask, iterations=4))
        if not count:
            return None
        ids = np.arange(1, count + 1)
        total = ndimage.sum(mask, labels, ids)
        inside = np.zeros(mask.shape, dtype=bool)
        inside[int(by1 - ey1):int(by2 - ey1), int(bx1 - ex1):int(bx2 - ex1)] = True
        within = ndimage.sum(mask & inside, labels, ids)
        keep = ids[(within >= 0.5 * total) & (total >= 0.002 * bw * bh)]
        if not len(keep):
            return None
        # подпись под фото («Твист с… 790₸») — отдельные фигуры целиком ниже главной: отбрасываем
        main = keep[np.argmax(total[keep - 1])]
        rows = ndimage.find_objects(labels)
        main_bottom = rows[main - 1][0].stop
        keep = [k for k in keep if rows[k - 1][0].start < main_bottom]
        obj = np.isin(labels, keep) & mask
        ys, xs = np.nonzero(obj)
        r0, r1, c0, c1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        if r1 - r0 < 50 or c1 - c0 < 50:
            return None

        cut = ((r0 <= 1 and ey1 == 0) or (r1 >= region.shape[0] - 1 and ey2 == H)
               or (c0 <= 1 and ex1 == 0) or (c1 >= region.shape[1] - 1 and ex2 == W))
        if cut:
            return None  # предмет обрезан краем фрагмента — возьмём с соседнего, где он целиком
        if r0 <= 1 or c0 <= 1 or r1 >= region.shape[0] - 1 or c1 >= region.shape[1] - 1:
            continue     # упёрся в край области — расширяем
        if H - (ey1 + r1) < max(40, 0.3 * (r1 - r0)):
            return None  # под фото нет места для подписи — фото чужой карточки, обрезанной снизу

        # центр корпуса без ручки кружки: столбцы, где предмет «высокий» (ручка тонкая и в них не попадает).
        # Маска без дыр: белая середина пачки или чашки — тоже предмет; разрывы контура сначала закрываем
        k = max(3, round(0.04 * max(r1 - r0, c1 - c0)))
        padded = np.pad(obj[r0:r1, c0:c1], k)
        filled = ndimage.binary_fill_holes(ndimage.binary_closing(padded, iterations=k))[k:-k, k:-k]
        heights = filled.sum(axis=0)
        body = np.flatnonzero(heights >= 0.75 * heights.max())
        center = (body[0] + body[-1] + 1) / 2 if len(body) else (c1 - c0) / 2
        # ручка сдвигает корпус от центра не больше чем на 15% ширины; больше — маска неполная (белое на белом)
        center = c0 + min(max(center, 0.35 * (c1 - c0)), 0.65 * (c1 - c0))

        # кусок фото с запасом фона вокруг предмета, но без чужого: соседних карточек, подписи
        margin = round(0.12 * max(r1 - r0, c1 - c0))
        foreign = mask & ~np.isin(labels, keep)
        def free(lines):  # сколько строк/столбцов фона можно взять, пока не начнётся чужое
            n = 0
            for line in lines[:margin]:
                if line.any():
                    break
                n += 1
            return max(0, n - 2)
        top = free(foreign[r0 - 1::-1, c0:c1] if r0 else foreign[:0])
        bottom = free(foreign[r1:, c0:c1])
        left = free(foreign[r0:r1, c0 - 1::-1].T if c0 else foreign[:0])
        right = free(foreign[r0:r1, c1:].T)
        X0, Y0 = ex1 + c0 - left, ey1 + r0 - top
        img = tile.crop((X0, Y0, ex1 + c1 + right, ey1 + r1 + bottom))
        box = (left, top, left + c1 - c0, top + r1 - r0)
        return img, box, ex1 + center - X0
    return None


# ───────── запрос к модели

# Модель отвечает короткими ключами — меньше текста: быстрее, меньше упирается в лимит токенов и реже обрывается.
# Скрипт переводит их обратно в формат сайта (expand_keys); ответы с полными ключами тоже понимает.
KEY_MAPPING = {
    'cats': 'categories', 'mods': 'modifier_groups', 'itms': 'items',
    'cid': 'category_id', 'sec': 'section', 'n': 'name', 'ic': 'icon', 'desc': 'description', 'ing': 'ingredients',
    'vars': 'variants', 'm': 'measure', 'p': 'price',
    'nut': 'nutrition', 'cal': 'calories', 'pro': 'proteins', 'fat': 'fats', 'carb': 'carbs',
    't': 'type', 'app': 'applies_to', 'opts': 'options', 'def': 'default',
}
SHORT_KEYS = {v: k for k, v in KEY_MAPPING.items()}
# это скрипт заполняет сам — модели писать не нужно
NOT_FOR_MODEL = {'image_url', 'prep_time_min', 'is_special', 'variant_id', 'order'}


def _rename_keys(obj, mapping, drop=()):
    if isinstance(obj, dict):
        return {mapping.get(k, k): _rename_keys(v, mapping, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [_rename_keys(x, mapping, drop) for x in obj]
    return obj


def expand_keys(data):
    return _rename_keys(data, KEY_MAPPING)


def shorten_keys(data):
    return _rename_keys(data, SHORT_KEYS, NOT_FOR_MODEL)


PROMPT_EXAMPLE = {
    'modifier_groups': [],
    'items': [
        {'section': 'Кофе с молоком', 'category_id': 'coffee', 'name': 'Капучино', 'icon': '☕', 'description': None, 'ingredients': None,
         'variants': [{'measure': '250 мл', 'price': 1190, 'nutrition': None},
                      {'measure': '350 мл', 'price': 1390, 'nutrition': None}]},
        {'section': 'Авторские напитки', 'category_id': 'coffee', 'name': 'Раф лавандовый', 'icon': '☕',
         'description': 'Эспрессо, сливки и лавандовый сироп', 'ingredients': None,
         'variants': [{'measure': None, 'price': 1590,
                       'nutrition': {'calories': 280, 'proteins': None, 'fats': None, 'carbs': None}}]},
    ],
}


def build_prompt(etalon, categories):
    cats = '\n'.join(f'  - {c["id"]} — {c["name"]}' for c in categories if c['id'] != 'other')
    template = shorten_keys(etalon)
    template.pop('cats', None)  # разделы скрипт собирает сам — по sec у позиций
    template['itms'] = [{'sec': '', **{k: v for k, v in item.items() if k != 'id'}}  # id строится из названия
                        for item in template.get('itms', [])]
    return f"""На фото — страница меню кофейни. Перепиши ВСЕ позиции с фото в JSON строго по шаблону.

Ключи в шаблоне сокращены: itms — позиции, mods — группы добавок, sec — раздел, cid — тип позиции,
n — название, ic — эмодзи, desc — описание, ing — состав, vars — варианты (размеры), m — объём/вес,
p — цена, nut — КБЖУ (cal, pro, fat, carb), t — тип, app — к каким разделам, opts — варианты, def — по умолчанию.

Правила:
1. Ответ — только JSON-объект, без пояснений и без ```.
2. Ничего не выдумывай. Чего нет на фото (описание, состав, объём/вес, КБЖУ) — пиши null.
3. sec — заголовок раздела, под которым позиция стоит на фото, слово в слово, как написано
   («чёрный кофе», «back to 00's movies», «сэндвичи и роллы»). У всех позиций под одним заголовком — один sec.
   Вкладки и кнопки вверху экрана («напитки», «витрина», «магазинная полка») — не заголовки разделов.
4. cid — тип позиции (нужен для цвета и рекомендаций), только один из:
{cats}
   Если ничего не подходит — other. Напитки (в том числе глинтвейн, какао, урбеч, молочные коктейли) —
   только coffee, tea, cocoa или cold_drinks, никогда не блюда.
5. p — число без пробелов и знака валюты: «1 290 ₸» → 1290.
6. Один напиток в нескольких размерах (S/M/L, 250/350 мл) — одна позиция с несколькими vars,
   в m пиши объём или вес как на фото («350 мл», «150 г»), если не указан — null.
7. Добавки с доплатой (сиропы, альтернативное молоко, доп. шот), если они есть на фото, — в mods:
   t "single" — выбирается одно (молоко), "multi" — несколько (сиропы); app — id разделов.
   Если добавок на фото нет — "mods": [].
8. Названия пиши как на фото, исправляя только явные ошибки распознавания.
9. Если на фото нет меню — верни {{"mods": [], "itms": []}}.
10. Фото может быть фрагментом длинного меню. Карточку, обрезанную верхним или нижним краем
    (не видно названия или цены целиком), пропусти — она целиком есть на соседнем фрагменте.
11. Цену читай очень внимательно, цифра за цифрой: 990, 1090 и 1290 — разные цены.
12. Блоки «Популярное», «Хиты», «Рекомендуем», «Новинки» — не разделы: позиции из них всё равно
    переписывай с sec: null, cid выбирай по смыслу позиции.
13. ic — один эмодзи, который точнее всего изображает позицию: 🍋 лимонад, 🍒 вишнёвый колд брю,
    🥜 урбеч, 🍵 матча, 🍫 горячий шоколад, 🥛 молочный коктейль, ☕ классический кофе.

Шаблон (пустой):
{json.dumps(template, ensure_ascii=False, separators=(',', ':'))}

Пример правильно заполненного ответа (позиции придуманы — бери данные только с фото):
{json.dumps(shorten_keys(PROMPT_EXAMPLE), ensure_ascii=False, separators=(',', ':'))}"""


def extract_json(text):
    """Достаёт JSON из ответа модели, даже если она обернула его в ``` или добавила текст."""
    text = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('в ответе нет JSON')
    return json.loads(text[start:end + 1])


RETRY_WAITS = (5, 15, 30, 60)  # секунды между попытками: сервер перегружен — даём ему передохнуть
# Лимит ключа llm.alem.ai — 15 запросов в минуту: держим паузу между запросами, чтобы не упираться в него
MIN_INTERVAL = float(os.environ.get('GEMMA_MIN_INTERVAL', '4.5'))
_last_call = [0.0]


def _pace():
    wait = _last_call[0] + MIN_INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def call_model(client, model, messages, max_tokens):
    """Запрос к модели с повторами: при перегрузке, лимите запросов, сетевом сбое и битом JSON.
    Возвращает (JSON из ответа, текст ответа)."""
    last_error, last_exc = None, None
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            _pace()
            resp = client.chat.completions.create(model=model, temperature=0, max_tokens=max_tokens, messages=messages,
                                                  response_format={'type': 'json_object'})  # ответ — только JSON
            text = resp.choices[0].message.content or ''
            return expand_keys(extract_json(text)), text
        except (ValueError, json.JSONDecodeError) as e:
            last_error, last_exc = f'модель вернула некорректный JSON: {e}', None
        except Exception as e:  # сеть, лимиты, перегрузка, неверный ключ — сообщение от сервера
            last_exc = e
            status = getattr(e, 'status_code', None)
            last_error = f'{type(e).__name__}{f" {status}" if status else ""}: {e}'
            if status in (400, 401, 403, 404):
                break  # неверный ключ, модель или запрос — повторять бессмысленно
        if attempt == len(RETRY_WAITS):
            break
        wait = RETRY_WAITS[attempt]
        # сервер может сам сказать, сколько ждать (Retry-After)
        headers = getattr(getattr(last_exc, 'response', None), 'headers', None) or {}
        if str(headers.get('retry-after', '')).isdigit():
            wait = max(wait, min(120, int(headers['retry-after'])))
        print(f'    попытка {attempt + 1} не удалась ({last_error[:150]}), повтор через {wait} с')
        time.sleep(wait)
    raise RuntimeError(last_error)


def ask_model(client, model, prompt, data_url):
    """Распознаёт меню на одном фото или фрагменте."""
    return call_model(client, model, [
        {'role': 'system', 'content': 'Ты точно переписываешь меню кофеен с фотографий в JSON. Отвечаешь только JSON.'},
        {'role': 'user', 'content': [
            {'type': 'text', 'text': prompt},
            {'type': 'image_url', 'image_url': {'url': data_url}},
        ]},
    ], max_tokens=8192)


# ───────── приведение ответа модели к формату сайта

TR = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюяәғқңөұүһі',
              ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
               'u', 'f', 'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya',
               'a', 'g', 'k', 'n', 'o', 'u', 'u', 'h', 'i']))


def slug(text):
    s = ''.join(TR.get(ch, ch) for ch in str(text).lower())
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def text_or_null(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def icon_or_null(v):
    """Эмодзи позиции: одна-две картинки без букв и цифр, иначе null (на сайте будет значок раздела)."""
    s = text_or_null(v)
    return s if s and len(s) <= 8 and not re.search(r'[\w\s]', s) else None


def tidy_name(v):
    """«КОФЕ» → «Кофе»: в меню заголовки часто набраны капсом, на сайте это выглядит крикливо.
    Короткие слова (KFC, РАФ) не трогаем. Висящий дефис («Чай клубника-малина-» — название
    обрезано в самом меню) убираем."""
    s = text_or_null(v)
    s = s.rstrip(' -–—') or s if s else s
    return s[0] + s[1:].lower() if s and s.isupper() and len(s) > 3 else s


def to_price(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return round(v) if v > 0 else None
    if isinstance(v, str):
        s = re.sub(r'[\s ₸тгTKZkzт.]+$', '', v.strip())       # «1 290 ₸», «990тг»
        s = re.sub(r'[\s ]', '', s)
        if re.fullmatch(r'\d{1,3}([.,]\d{3})+', s):  # «1.290» / «1,290» — разделитель тысяч
            s = re.sub(r'[.,]', '', s)
        s = s.replace(',', '.')
        if re.fullmatch(r'\d+(\.\d+)?', s):
            return round(float(s)) or None
    return None


def to_number(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace(',', '.'))
    except ValueError:
        return None


def nutrition(v):
    if not isinstance(v, dict):
        return None
    n = {k: to_number(v.get(k)) for k in ('calories', 'proteins', 'fats', 'carbs')}
    # одни нули/пусто — значит КБЖУ на фото не было
    return n if any(x not in (None, 0) for x in n.values()) else None


def name_stem(name):
    """Название для сравнения и признак, что оно обрезано на карточке многоточием («Батч смородиновы...»)."""
    key = re.sub(r'\s+', ' ', name.lower().replace('ё', 'е')).strip()
    stem = re.sub(r'\s*(\.{2,}|…)$', '', key).strip()
    return (stem, True) if stem != key and len(stem) >= 4 else (key, False)


POPULAR_RE = re.compile(r'популяр|хит|рекоменд|бестселл|новинк|popular|best|hits?\b', re.I)


class MenuBuilder:
    """Копит разделы, добавки и позиции со всех фото и следит, чтобы id не повторялись.
    Разделы — как на фото (заголовок над карточками), а стиль раздела (цвет, значок, рекомендации) —
    из общих стилей coffee-menu/data/categories.json по типу позиций в нём."""

    def __init__(self, cafe_id, styles):
        self.cafe_id = cafe_id
        self.styles = {s['id']: s for s in styles}
        self.sections = {}         # ключ названия → название раздела с фото (порядок — как на фото)
        self.groups = {}           # id → группа добавок
        self.items = []
        self.item_ids = set()
        self.by_key = {}           # название → id позиции (чтобы привязать фото)
        self.warnings = []
        self.no_price = []         # позиции без цены: (откуда, название, ключ, обрезано, раздел)

    def style_id(self, raw):
        cid = str(raw or '').strip()
        return cid if cid in self.styles else 'other'

    def section(self, name):
        """Название раздела с фото или None — для «Популярного» и подобных витрин."""
        name = tidy_name(name)
        if not name or POPULAR_RE.search(name):
            return None
        key = name.lower().replace('ё', 'е')
        return self.sections.setdefault(key, name)

    def add(self, data, source):
        if not isinstance(data, dict):
            self.warnings.append(f'{source}: ответ не является объектом JSON')
            return 0

        # старые ответы (из кэша) без section: название раздела — из categories по типу
        names = {self.style_id(c.get('id')): c.get('name') for c in data.get('categories') or [] if isinstance(c, dict)}

        for g in data.get('modifier_groups') or []:
            self.add_group(g, source)

        added = 0
        for raw in data.get('items') or []:
            if self.add_item(raw, names, source):
                added += 1
        return added

    def add_group(self, g, source):
        if not isinstance(g, dict) or not text_or_null(g.get('name')):
            return
        gid = slug(g.get('id') or g.get('name')) or 'extra'
        options = []
        for o in g.get('options') or []:
            if not isinstance(o, dict) or not text_or_null(o.get('name')):
                continue
            option = {'id': slug(o.get('id') or o['name']) or f'opt{len(options) + 1}',
                      'name': o['name'].strip(), 'price': to_price(o.get('price')) or 0}
            if o.get('default') is True:
                option['default'] = True
            options.append(option)
        if not options:
            return
        group = {
            'id': gid,
            'name': tidy_name(g['name']),
            'type': 'multi' if g.get('type') == 'multi' else 'single',
            'applies_to': [c for c in (g.get('applies_to') or []) if c in self.styles],
            'options': options,
        }
        if gid in self.groups:  # та же группа на другом фото — добавляем новые варианты
            known = {o['id'] for o in self.groups[gid]['options']}
            self.groups[gid]['options'] += [o for o in options if o['id'] not in known]
        else:
            self.groups[gid] = group

    def add_item(self, raw, names, source):
        if not isinstance(raw, dict) or not text_or_null(raw.get('name')):
            return False
        name = tidy_name(raw['name'])
        style = self.style_id(raw.get('category_id'))
        section = self.section(raw['section'] if 'section' in raw else names.get(style))

        key = re.sub(r'\s+', ' ', name.lower().replace('ё', 'е'))
        variants = []
        for v in raw.get('variants') or []:
            if not isinstance(v, dict):
                continue
            price = to_price(v.get('price'))
            if price is None:
                continue
            variants.append({'measure': text_or_null(v.get('measure')), 'price': price, 'nutrition': nutrition(v.get('nutrition'))})
        if not variants and to_price(raw.get('price')):  # модель могла написать цену прямо у позиции
            variants.append({'measure': None, 'price': to_price(raw['price']), 'nutrition': None})
        same_key, cut = name_stem(name)
        if not variants:
            # цены не видно — не страшно, если позиция есть на другом фрагменте, где цена видна (проверим в конце)
            self.no_price.append((source, name, same_key, cut, section))
            return False

        item = self.find_same(same_key, cut, section, variants[0]['price'])
        if item:
            # уже есть: с другого фото, из перекрытия фрагментов или из «Популярного»
            if item['_cut'] and not cut:   # там название было обрезано («Лимонад Смородина-...») — берём полное
                item.update(name=name, _stem=same_key, _cut=False)
                self.by_key[key] = item['id']
            if section and not item['_section']:
                # была только в «Популярном», а теперь нашлась в своём разделе — переносим туда
                item['_section'] = section
                self.items.remove(item)
                self.items.append(item)
            return False

        # id — всегда из названия: модель иногда повторяет один id у разных позиций
        stem = slug(name) or 'item'
        item_id = f'item_{stem}'
        n = 2
        while item_id in self.item_ids:
            item_id = f'item_{stem}_{n}'
            n += 1
        self.item_ids.add(item_id)
        stem = item_id.removeprefix('item_')

        ingredients = [str(x).strip() for x in raw.get('ingredients') or [] if str(x).strip()]
        self.by_key[key] = item_id
        self.items.append({
            '_section': section,
            '_style': style,
            '_stem': same_key,
            '_cut': cut,
            'id': item_id,
            'category_id': None,           # id раздела — в result(), когда известны все разделы
            'name': name,
            'image_url': None,             # проставляется, если фото позиции удалось вырезать
            'icon': icon_or_null(raw.get('icon')),
            'description': text_or_null(raw.get('description')),
            'ingredients': ingredients or None,
            'prep_time_min': None,
            'is_special': False,
            'variants': [{'variant_id': f'var_{stem}_{"std" if len(variants) == 1 else i + 1}', **v}
                         for i, v in enumerate(variants)],
        })
        return True

    def find_same(self, stem, cut, section, price):
        """Та же позиция, уже добавленная раньше: название совпадает (или одно — обрезанное начало другого),
        цена та же, а раздел тот же или неизвестен (в «Популярном»). Одинаковые названия с другой ценой
        или в другом разделе — разные позиции: «Espresso Blend, для эспрессо...» за 3490 (200 г) и за 13990 (1 кг)."""
        for item in self.items:
            same_name = (item['_stem'] == stem or (cut and item['_stem'].startswith(stem))
                         or (item['_cut'] and stem.startswith(item['_stem'])))
            if (same_name and price in (None, item['variants'][0]['price'])
                    and (not section or not item['_section'] or item['_section'] == section)):
                return item
        return None

    def find_id(self, name):
        """id позиции по названию, как его написала модель (без учёта регистра, ё/е и пробелов).
        На карточке длинное название бывает обрезано («Батч смородиновы...») — тогда ищем позицию,
        чьё название начинается так же, если такая ровно одна."""
        key = re.sub(r'\s+', ' ', (tidy_name(name) or '').lower().replace('ё', 'е'))
        if key in self.by_key:
            return self.by_key[key]
        stem = re.sub(r'[.…]+$', '', key).strip()
        if len(stem) >= 4:
            matches = [k for k in self.by_key if k.startswith(stem)]
            if len(matches) == 1:
                return self.by_key[matches[0]]
        return None

    def result(self):
        from collections import Counter
        # позиции, раздел которых так и не встретился, — в раздел по типу («Кофе», «Десерты»…)
        for item in self.items:
            if not item['_section']:
                item['_section'] = self.section(self.styles.get(item['_style'], {}).get('name') or 'Другое')
        for source, name, key, cut, section in self.no_price:
            if not self.find_same(key, cut, section, None):
                self.warnings.append(f'{source}: «{name}» пропущена — не распознана цена')
        self.no_price = []
        # разделы — в порядке, в котором на фото встречаются их позиции
        first = {}
        for n, item in enumerate(self.items):
            first.setdefault(item['_section'], n)
        categories, ids = [], {}
        for name in sorted(first, key=first.get):
            members = [i for i in self.items if i['_section'] == name]
            style = Counter(i['_style'] for i in members).most_common(1)[0][0]
            cid = base = slug(name) or style
            n = 2
            while cid in ids.values():
                cid, n = f'{base}_{n}', n + 1
            ids[name] = cid
            categories.append({'id': cid, 'style': style, 'name': name,
                               'icon': self.styles.get(style, {}).get('emoji'), 'order': len(categories) + 1})
        items = [{**{k: v for k, v in i.items() if not k.startswith('_')}, 'category_id': ids[i['_section']]}
                 for i in self.items]
        return {'categories': categories, 'modifier_groups': list(self.groups.values()), 'items': items}


def last_section_name(data):
    """Название раздела, которым заканчивается ответ модели по фрагменту, — подсказка для следующего."""
    if not isinstance(data, dict):
        return None
    items = [i for i in data.get('items') or [] if isinstance(i, dict)]
    for item in reversed(items):
        sec = text_or_null(item.get('section'))
        if sec and not POPULAR_RE.search(sec):
            return sec
    names = {c.get('id'): c.get('name') for c in data.get('categories') or [] if isinstance(c, dict)}
    if items and names.get(items[-1].get('category_id')):
        return text_or_null(names[items[-1]['category_id']])
    return None


# ───────── целая вкладка: сведения, меню, фотографии, ответы модели

def notice(level, text):
    """Сообщение в лог; в GitHub Actions — ещё и аннотация на странице задачи."""
    print(f'::{level}::{text}' if os.environ.get('GITHUB_ACTIONS') else f'  {"⚠" if level == "warning" else "✗"} {text}')


def cafe_info(photos_dir, cafe_id):
    """Необязательный cafe.json рядом с фото: {"name": "...", "address": "...", "city": "...", "hours": "..."}."""
    info = load_json(photos_dir / 'cafe.json', {}) or {}
    name = text_or_null(info.get('name')) or cafe_id.replace('_', ' ').title()
    result = {k: text_or_null(info.get(k)) for k in ('address', 'city', 'hours', 'logo')} | {'name': name}
    # Настройки модулей переносятся из конфига, модель их не генерирует.
    # Отсутствие блока отключает модули при следующем распознавании.
    result['modules'] = {key: info['modules'][key] for key in ('pickup', 'delivery')
                         if isinstance(info.get('modules'), dict) and isinstance(info['modules'].get(key), dict)}
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def logo_file(photos_dir, info):
    """Логотип из папки исходников; поддерживаем также прежний путь от корня сайта."""
    if not info.get('logo'):
        return None
    for path in (photos_dir / info['logo'], SITE / info['logo']):
        if path.is_file():
            return path.resolve()
    raise ValueError(f'Логотип не найден: {info["logo"]}')


def write_tab(folder, cafe_id, info, menu, crops, logo=None):
    """Все файлы заведения в одной папке. Индекс обновляется после записи вкладки."""
    folder = folder.resolve()
    on_site = folder.parent == (SITE / 'tabs').resolve()
    previous = load_json(folder / 'cafe.json', {}) or {}
    if on_site and (folder / 'menu.json').exists() and previous.get('source') != 'photos':
        raise ValueError(f'Вкладка «{cafe_id}» создана вручную; используйте --out для отдельной копии')
    folder.mkdir(parents=True, exist_ok=True)
    entry = {'id': cafe_id, 'currency': 'KZT', 'theme': {'accent': None}, **previous,
             **{k: v for k, v in info.items() if v is not None and k != 'logo'}, 'source': 'photos'}
    entry.setdefault('logo', None)
    for key in ('address', 'city', 'hours'):
        entry.setdefault(key, None)
    if logo:
        entry['logo'] = f'logo{logo.suffix.lower()}'
        target = folder / entry['logo']
        if logo.resolve() != target.resolve():
            shutil.copy2(logo, target)
    for item in menu['items']:
        img = crops.get(item['id'])
        if img is None:
            continue
        (folder / 'images').mkdir(exist_ok=True)
        img.thumbnail((600, 600))
        item['image_url'] = f'images/{item["id"]}.jpg'
        img.save(folder / item['image_url'], 'JPEG', quality=85, optimize=True)
    # фото позиций, которых в новом меню нет или у которых теперь эмодзи, — убираем (archive/ не трогаем)
    used = {item['image_url'] for item in menu['items'] if item['image_url']}
    for old in (folder / 'images').glob('item_*.jpg'):
        if f'images/{old.name}' not in used:
            old.unlink()
    write_json(folder / 'menu.json', menu)
    write_json(folder / 'cafe.json', entry)
    if on_site:
        index_path = SITE / 'tabs' / 'index.json'
        index = load_json(index_path, {}) or {}
        folders = index.setdefault('tabs', [])
        if folder.name not in folders:
            folders.append(folder.name)
        write_json(index_path, index)


def run_secretbox_mode(args, parser, photos_dir, api_key, base_url, model):
    if not args.secretbox_shop or not re.fullmatch(r'[A-Za-z0-9_-]+', args.secretbox_shop):
        parser.error('--secretbox-shop должен быть id кофейни, например Ayu')
    if args.menu_mode not in ('replace', 'merge'):
        parser.error('для режима SecretBox укажите --menu-mode replace или --menu-mode merge')
    if args.cafe_id or args.out or args.from_cache or args.publish or not args.photos_from_menu:
        parser.error('--secretbox-shop нельзя сочетать с параметрами режима coffee-menu')
    if args.max_width <= 0:
        parser.error('--max-width должен быть больше нуля')

    shop_path = SECRETBOX_OBJECTS / f'{args.secretbox_shop}_menu.txt'
    if not shop_path.is_file():
        shops = sorted(path.stem.removesuffix('_menu') for path in SECRETBOX_OBJECTS.glob('*_menu.txt'))
        parser.error(f'Меню «{args.secretbox_shop}» не найдено в objects. Доступны: {", ".join(shops)}')

    if photos_dir.is_file() and photos_dir.suffix.lower() in IMAGE_EXT:
        photos = [photos_dir]
    elif photos_dir.is_dir():
        photos = sorted(
            path for path in photos_dir.glob('*')
            if path.is_file() and path.suffix.lower() in IMAGE_EXT
        )
    else:
        parser.error(f'Папка или изображение со скриншотами не найдены: {photos_dir}')
    if not photos:
        parser.error(f'В папке {photos_dir} нет изображений ({", ".join(sorted(IMAGE_EXT))})')

    default_out = HERE / 'output' / 'secretbox-drafts' / (
        f'{args.secretbox_shop}_{time.strftime("%Y%m%d_%H%M%S")}_menu.txt'
    )
    draft_path = Path(args.draft_out).resolve() if args.draft_out else default_out.resolve()
    if (draft_path == shop_path.resolve() or SECRETBOX_OBJECTS.resolve() in draft_path.parents
            or draft_path in {photo.resolve() for photo in photos}):
        parser.error('Черновик нельзя записать поверх исходного меню или скриншота')
    if draft_path.suffix.lower() != '.txt':
        parser.error('Путь черновика должен оканчиваться на .txt')
    if draft_path.exists():
        parser.error(f'Файл черновика уже существует: {draft_path}; укажите другой --draft-out')

    try:
        from openai import OpenAI
    except ImportError:
        sys.exit('Не установлена библиотека openai. Выполните: py -m pip install -r driver\\requirements.txt')
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180, max_retries=0)

    recognized = []
    failed = []
    print(f'Модель: {model} ({base_url})')
    print(f'Кофейня: {args.secretbox_shop}, скриншотов: {len(photos)}, режим: {args.menu_mode}\n')
    for photo_index, photo in enumerate(photos, 1):
        tiles = image_tiles(photo, args.max_width)
        print(f'[{photo_index}/{len(photos)}] {photo.name}' +
              (f' — {len(tiles)} фрагм.' if len(tiles) > 1 else ''))
        for tile_index, (_, data_url) in enumerate(tiles, 1):
            label = f'{photo.name} [{tile_index}/{len(tiles)}]' if len(tiles) > 1 else photo.name
            try:
                items = ask_secretbox_menu(client, model, data_url)
            except Exception as error:
                failed.append(f'{label}: {error}')
                print(f'    ERROR: {failed[-1]}')
                continue
            recognized.extend(items)
            if items:
                print(f'    OK: {label}: позиций {len(items)}')
            else:
                print(f'    WARNING: {label}: позиции с ценами не найдены')
                failed.append(f'{label}: позиции с ценами не найдены')

    if failed:
        sys.exit('Не все изображения распознаны; черновик не создан:\n  ' + '\n  '.join(failed))
    if not recognized:
        sys.exit('Не распознано ни одной позиции; черновик не создан')

    if args.menu_mode == 'merge':
        try:
            existing = read_secretbox_menu(shop_path)
            items, updated, added = merge_secretbox_menu(existing, recognized)
        except ValueError as error:
            sys.exit(f'Не удалось безопасно объединить меню: {error}')
        unchanged = len(existing) - updated
        print(f'\nОбъединение: обновлено {updated}, добавлено {added}, без изменений {unchanged}')
    else:
        try:
            items, _, _ = merge_secretbox_menu([], recognized)
        except ValueError as error:
            sys.exit(f'Распознаны противоречивые данные; черновик не создан: {error}')
        print(f'\nЗамена меню целиком: {len(items)} позиций')

    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text('\n'.join(secretbox_line(item) for item in items) + '\n', encoding='utf-8')
    print(f'Черновик сохранён: {draft_path}')
    print('Проверьте черновик, затем загрузите его через Update this menu -> Upload .txt.')
    print('Исходное меню не изменено; загрузка файла заменит меню выбранного кафе целиком.')


# ───────── запуск

def main():
    parser = argparse.ArgumentParser(description='Распознавание меню по фото для coffee-menu или SecretBox')
    parser.add_argument('photos', help='папка заведения с cafe.json и скриншотами, например venues/dodo_pizza')
    parser.add_argument('--cafe-id', help='id кофейни латиницей, например ayu_menu (по умолчанию — имя папки)')
    parser.add_argument('--out', help='папка готовой вкладки (по умолчанию coffee-menu/tabs/<id>/)')
    parser.add_argument('--secretbox-shop', help='вместо coffee-menu подготовить черновик для кафе SecretBox')
    parser.add_argument('--menu-mode', choices=('replace', 'merge'),
                        help='replace — полное меню со скриншотов; merge — обновить совпавшие позиции и добавить новые')
    parser.add_argument('--draft-out', help='путь .txt-черновика SecretBox (по умолчанию создаётся в driver/output)')
    parser.add_argument('--max-width', type=int, default=1600,
                        help='ширина, до которой уменьшается фото, px (длинные фото режутся на фрагменты по высоте)')
    parser.add_argument('--no-photos', dest='photos_from_menu', action='store_false',
                        help='не вырезать фото позиций из меню (быстрее: один запрос к модели на фрагмент)')
    parser.add_argument('--from-cache', action='store_true',
                        help='брать сохранённые ответы модели (raw/ в папке вкладки) вместо новых запросов — '
                             'чтобы заново собрать меню и вырезать фото после правок скрипта')
    parser.add_argument('--publish', action='store_true',
                        help='совместимость со старым запуском: теперь вкладка по умолчанию сохраняется на сайт')
    args = parser.parse_args()

    load_env(HERE / '.env')
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://llm.alem.ai/v1').strip()
    model = os.environ.get('GEMMA_MODEL', 'gemma4').strip()
    if not api_key or api_key == 'Ваш API_KEY':
        sys.exit('Нет API-ключа: задайте OPENAI_API_KEY в driver/.env (OPENAI_API_KEY=...)')

    photos_dir = Path(args.photos)
    if not photos_dir.is_absolute():
        photos_dir = (Path.cwd() / photos_dir) if (Path.cwd() / photos_dir).exists() else HERE / photos_dir
    photos_dir = photos_dir.resolve()
    if args.secretbox_shop:
        run_secretbox_mode(args, parser, photos_dir, api_key, base_url, model)
        return
    if args.menu_mode or args.draft_out:
        parser.error('--menu-mode и --draft-out можно использовать только вместе с --secretbox-shop')
    cafe_id = slug(args.cafe_id or photos_dir.name)
    if not cafe_id:
        parser.error('Не удалось получить id заведения; задайте --cafe-id латиницей')
    info = cafe_info(photos_dir, cafe_id)
    try:
        logo = logo_file(photos_dir, info)
    except ValueError as e:
        parser.error(str(e))
    photos = sorted(p for p in photos_dir.glob('*') if p.is_file() and p.suffix.lower() in IMAGE_EXT
                    and p.resolve() != logo)
    if not photos:
        sys.exit(f'В папке {photos_dir} нет фото ({", ".join(sorted(IMAGE_EXT))})')

    out = Path(args.out).resolve() if args.out else SITE / 'tabs' / cafe_id
    if out.suffix.lower() == '.json':
        parser.error('--out теперь принимает папку вкладки, например output/tabs/my_cafe')
    if out.parent.resolve() == (SITE / 'tabs').resolve():
        previous = load_json(out / 'cafe.json', {}) or {}
        if (out / 'menu.json').exists() and previous.get('source') != 'photos':
            out = HERE / 'output' / 'tabs' / cafe_id
            notice('warning', f'Ручное меню сохранено. Новая вкладка будет записана отдельно: {out}')
    raw_dir = out / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)

    try:
        from openai import OpenAI
    except ImportError:
        sys.exit('Не установлена библиотека openai. Выполните: pip install -r requirements.txt')
    # повторы делает call_model (с паузами), встроенные повторы библиотеки выключены
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180, max_retries=0)

    etalon = load_json(HERE / 'etalon.json')
    styles = (load_json(SITE / 'data' / 'categories.json', {}) or {}).get('categories', [])
    prompt = build_prompt(etalon, styles)

    print(f'Модель: {model} ({base_url})')
    print(f'Кофейня: {cafe_id}, фото: {len(photos)}\n')

    builder = MenuBuilder(cafe_id, styles)
    failed = []
    crops = {}  # id позиции → вырезанное фото (сохраняются в конце, когда ясно, куда пишется меню)
    for n, photo in enumerate(photos, 1):
        tiles = image_tiles(photo, args.max_width)
        print(f'[{n}/{len(photos)}] {photo.name}' + (f' — {len(tiles)} фрагм.' if len(tiles) > 1 else ''))
        last_section = None  # раздел, которым закончился предыдущий фрагмент
        for k, (tile_img, tile) in enumerate(tiles, 1):
            label = f'{photo.name} [{k}/{len(tiles)}]' if len(tiles) > 1 else photo.name
            context = (f'\n\nЭто фрагмент {k} из {len(tiles)} одного длинного меню. На предыдущем фрагменте последним '
                       f'был раздел «{last_section}» — у позиций в начале этого фрагмента до первого заголовка '
                       f'sec: «{last_section}».'
                       if k > 1 and last_section else '')
            suffix = f'_{k:02d}' if len(tiles) > 1 else ''
            raw_menu = raw_dir / f'{photo.stem}{suffix}.json'
            raw_boxes = raw_dir / f'{photo.stem}{suffix}.photos.json'
            try:
                if args.from_cache and raw_menu.exists():  # ответ уже есть — модель не спрашиваем
                    text = raw_menu.read_text(encoding='utf-8')
                    data = expand_keys(extract_json(text))
                else:
                    data, text = ask_model(client, model, prompt + context, tile)
            except Exception as e:
                print(f'    ✗ {label}: не распознано: {e}')
                failed.append(label)
                continue
            raw_menu.write_text(text, encoding='utf-8')  # сырой ответ — для проверки и для --from-cache
            print(f'    ✓ {label}: новых позиций {builder.add(data, label)}')
            last_section = last_section_name(data) or last_section

            if tile_img is not None and args.photos_from_menu:
                found = 0
                if args.from_cache and raw_boxes.exists():
                    boxes = json.loads(raw_boxes.read_text(encoding='utf-8'))
                else:
                    boxes = ask_photos(client, model, tile)
                # рамки модели — рядом с сырыми ответами: по ним можно перепроверить вырезание без новых запросов
                raw_boxes.write_text(json.dumps(boxes, ensure_ascii=False), encoding='utf-8')
                for p in boxes:
                    item_id = builder.find_id(p['name'])
                    if item_id and item_id not in crops:
                        img = crop_photo(tile_img, p['box'])
                        if img is not None:
                            crops[item_id] = img
                            found += 1
                if found:
                    print(f'      фото позиций: {found}')

    menu = builder.result()
    if not menu['items']:
        # пустой результат не записываем — иначе он затёр бы прежнее меню
        notice('error', f'«{cafe_id}»: не распознано ни одной позиции, меню не изменено')
        sys.exit(1)

    if failed:
        # часть фрагментов не распознана — неполное меню на сайт не пишем, прежнее остаётся
        notice('error', f'«{cafe_id}»: не распознаны {", ".join(failed)} — меню на сайте не изменено. '
                        f'Запустите распознавание ещё раз.')
        sys.exit(1)
    write_tab(out, cafe_id, info, menu, crops, logo)

    with_icon = sum(1 for i in menu['items'] if not i['image_url'] and i['icon'])
    print(f'\nГотово: {out}')
    print(f'  разделов: {len(menu["categories"])}, позиций: {len(menu["items"])}, групп добавок: {len(menu["modifier_groups"])}')
    print(f'  фото из меню: {len(crops)} (в {out / "images"}), остальным — эмодзи: {with_icon}')
    for w in builder.warnings:
        notice('warning', w)
    if failed:
        notice('warning', f'не распознаны фото: {", ".join(failed)}')
    print('\nПроверьте распознанные цены и названия в menu.json.')


if __name__ == '__main__':
    main()

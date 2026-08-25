# app.py - 完整版（新增已知件数支持）
import datetime
import math
import os
import random
import re
import tempfile
import time
import threading
import numpy as np
from functools import lru_cache
from collections import defaultdict, Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple, Optional
import itertools
import json
from flask import Flask, render_template, request, jsonify, send_file, abort

try:
    from PIL import Image
    from PIL import ImageGrab
except ImportError:
    Image = None
    ImageGrab = None

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None

app = Flask(__name__)

APP_ICON_CANDIDATES = [
    r"C:\Users\armstrong\AppData\Local\Temp\codex-clipboard-f7ce13d5-3c99-481c-9c5e-128ff7ff3695.png",
    r"C:\Users\ARMSTR~1\AppData\Local\Temp\codex-clipboard-f7ce13d5-3c99-481c-9c5e-128ff7ff3695.png",
    r"C:\Users\armstrong\AppData\Local\Temp\codex-clipboard-bb06e5ac-fd80-49cc-8b1b-0b87ddbc1df2.png",
    r"C:\Users\ARMSTR~1\AppData\Local\Temp\codex-clipboard-bb06e5ac-fd80-49cc-8b1b-0b87ddbc1df2.png",
]

DECORATIVE_BADGE_CANDIDATES = [
    r"C:\Users\armstrong\AppData\Local\Temp\codex-clipboard-c20980cc-fbe8-4576-ade2-8d8452a79da0.png",
    r"C:\Users\ARMSTR~1\AppData\Local\Temp\codex-clipboard-c20980cc-fbe8-4576-ade2-8d8452a79da0.png",
    r"C:\Users\armstrong\AppData\Local\Temp\codex-clipboard-0fe5517b-806b-4d41-8ec9-07069353ed61.png",
    r"C:\Users\ARMSTR~1\AppData\Local\Temp\codex-clipboard-0fe5517b-806b-4d41-8ec9-07069353ed61.png",
]

BANNER_CANDIDATES = [
    r"C:\Users\armstrong\AppData\Local\Temp\codex-clipboard-35e0a06f-8e30-44d2-9ef4-afd7a40c4e21.png",
    r"C:\Users\ARMSTR~1\AppData\Local\Temp\codex-clipboard-35e0a06f-8e30-44d2-9ef4-afd7a40c4e21.png",
]


def _first_existing_path(candidates):
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


storage_lock = threading.RLock()
MAX_SEARCH_TIMEOUT = 60.0
MAX_OCR_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PRICE_LIST_ITEMS = 100


def _safe_int(value, default=None, min_value=None, max_value=None):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if min_value is not None and parsed < min_value:
        return default
    if max_value is not None and parsed > max_value:
        return default
    return parsed


def _parse_int_list(values, *, min_value=0, max_items=None):
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [item.strip() for item in values.split(",") if item.strip()]
    else:
        raw_values = list(values)

    parsed = []
    for raw in raw_values:
        number = _safe_int(raw, default=None, min_value=min_value)
        if number is None:
            raise ValueError(f"无效价格: {raw}")
        parsed.append(number)
        if max_items is not None and len(parsed) >= max_items:
            break
    return parsed


def _parse_red_prices(values):
    known_prices = []
    unknown_count = 0
    if values is None:
        return known_prices, unknown_count

    if isinstance(values, str):
        raw_values = [item.strip() for item in values.split(",") if item.strip()]
    else:
        raw_values = list(values)

    for raw in raw_values:
        token = str(raw).strip()
        if not token:
            continue
        if token.lower() in {"unknown", "-1", "none", "null"}:
            unknown_count += 1
            continue
        number = _safe_int(token, default=None, min_value=0)
        if number is None:
            raise ValueError(f"无效价格: {raw}")
        known_prices.append(number)

    return known_prices, unknown_count


def _read_json_file(path, default):
    with storage_lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default


def _write_json_file(path, payload, *, ensure_ascii=False, backup=False):
    directory = os.path.dirname(path) or BASE_DIR
    os.makedirs(directory, exist_ok=True)
    with storage_lock:
        if backup and os.path.exists(path):
            backup_file = path + ".bak"
            try:
                with open(path, "r", encoding="utf-8") as source:
                    old_data = source.read()
                with open(backup_file, "w", encoding="utf-8") as target:
                    target.write(old_data)
            except OSError:
                pass

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                dir=directory,
                suffix=".tmp",
                mode="w",
                encoding="utf-8",
            ) as tmp:
                tmp_path = tmp.name
                json.dump(payload, tmp, indent=2, ensure_ascii=ensure_ascii)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

# ========================== USER CONFIG ==========================
PRICES = [
    4975, 5041, 5047, 5555, 7500, 7547, 7610, 7648, 9040, 9938,
    11974, 11981, 12116, 12164, 13632, 15024, 15037, 15108, 15309,
    18031, 18193, 18288, 19926, 20238, 21012, 22297, 22336, 22770,
    22847, 27159, 27246, 30211, 30264, 37558, 38316, 51077, 60040,
    60285, 62456, 76591, 77777, 80754, 88888, 101403, 101537, 101554,
    111111, 124816, 202798, 271827
]

GOLD_SIZES = [
    1, 1, 1, 1, 2, 2, 2, 1, 1, 1,
    3, 4, 3, 3, 2, 3, 4, 4, 4, 4,
    3, 5, 4, 3, 3, 6, 6, 6, 6, 9,
    5, 6, 9, 2, 2, 25, 2, 2, 4, 6,
    3, 4, 6, 4, 12, 16, 4, 12, 20, 20
]

ERROR_MARGIN = 0.6
MAX_SEARCH_SIZE = 6
MAX_LIST_SIZE = 14
NUM_WORKERS = 1
MAX_REPEAT = 2
SPLIT_THRESHOLD = 5
MAX_COMBOS_PER_N = 500
DISPLAY_COMBOS = 10
ENABLE_COMBO_LIMIT = True
MAX_SEARCH_TIME = 30
UNKNOWN_RED_QUANTILES = (62000, 102000, 289000)
RED_BLEND_WEIGHT = 0.5
MIN_RED_SAMPLES = 10
RED_EXACT_LIMIT = 6
# =================================================================

# ========================== RED ITEM CONFIG ==========================
RED_PRICES_ALL = [
    29977, 31618, 50000, 52000, 59440, 61740, 61803, 76008, 78800,
    80608, 81088, 88600, 100000, 101860, 150051, 200201, 239342,
    240208, 260423, 280000, 288888, 300000, 366112, 500001, 577777,
    1314520, 5121024, 11235813, 20171210, 22668888
]

RED_SIZES = [
    2, 4, 1, 16, 16, 1, 1, 2, 2, 6,
    8, 4, 9, 3, 2, 4, 6, 9, 9, 2,
    5, 4, 6, 25, 6, 1, 2, 4, 25, 16
]

RED_PRICES = [p for p in RED_PRICES_ALL if p <= 1000000]

# 红色权重：以14万为基础价调整
DEFAULT_RED_WEIGHTS = [
    # 3-8万: 权重5.0
    5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0,
    # 8-10万: 权重4.0
    4.0, 4.0, 4.0, 4.0,
    # 15-20万: 权重3.0
    3.0, 3.0,
    # 20-30万: 权重2.5
    2.5, 2.5, 2.5, 2.5, 2.5, 2.5,
    # 30-58万: 权重2.0
    2.0, 2.0, 2.0,
]

RED_SIZES_FILTERED = RED_SIZES[:len(RED_PRICES)]
PRICES_SET = set(PRICES)
PRICE_TO_SIZE = dict(zip(PRICES, GOLD_SIZES))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_FILE = os.path.join(BASE_DIR, "red_weights.json")
HISTORY_FILE = os.path.join(BASE_DIR, "red_history.json")

def load_red_weights():
    data = _read_json_file(WEIGHTS_FILE, {})
    if isinstance(data, dict):
        weights = data.get("weights", DEFAULT_RED_WEIGHTS)
        if len(weights) >= len(RED_PRICES):
            return weights[:len(RED_PRICES)]
    return DEFAULT_RED_WEIGHTS.copy()

def save_red_weights(weights):
    _write_json_file(WEIGHTS_FILE, {"weights": weights})

RED_WEIGHTS = load_red_weights()

def load_history():
    data = _read_json_file(HISTORY_FILE, {"auctions": []})
    return data if isinstance(data, dict) else {"auctions": []}

def save_history(history):
    _write_json_file(HISTORY_FILE, history, ensure_ascii=False, backup=True)


OCR_ENGINE = None
OCR_ENGINE_LOCK = threading.Lock()


def _parse_ocr_number(raw):
    text = str(raw).strip()
    if not text:
        return None
    text = text.replace("，", ",").replace("．", ".").replace("。", "")
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    number = match.group(0).replace(",", "")
    if number.endswith("."):
        number = number[:-1]
    try:
        value = float(number)
    except ValueError:
        return None
    if value.is_integer():
        return int(value)
    return value


def _normalize_ocr_text(text):
    return re.sub(r"\s+", "", str(text)).replace("：", ":")


def _extract_number_after_keywords(text, keywords):
    source = _normalize_ocr_text(text)
    for keyword in keywords:
        idx = source.find(keyword)
        if idx == -1:
            continue
        tail = source[idx + len(keyword):]
        tail = tail.lstrip(":=：=为是")
        number = _parse_ocr_number(tail)
        if number is not None:
            return number
        match = re.search(r"\d[\d,]*(?:\.\d+)?", tail)
        if match:
            return _parse_ocr_number(match.group(0))
    return None


def _pick_ocr_line(lines, include_any=(), include_all=(), exclude_any=()):
    best_line = None
    best_score = -1
    for line in lines:
        normalized = _normalize_ocr_text(line)
        if include_all and any(token not in normalized for token in include_all):
            continue
        if include_any and not any(token in normalized for token in include_any):
            continue
        if exclude_any and any(token in normalized for token in exclude_any):
            continue
        score = sum(2 for token in include_all if token in normalized)
        score += sum(1 for token in include_any if token in normalized)
        if score > best_score:
            best_score = score
            best_line = normalized
    return best_line


@lru_cache(maxsize=8192)
def _gold_combo_size_info(combo_prices):
    sizes = tuple(get_gold_size(price) for price in combo_prices)
    return sizes, sum(sizes)


@lru_cache(maxsize=8192)
def _combo_covers_cached(combo_prices, need_items):
    if not need_items:
        return True
    have = Counter(combo_prices)
    return all(have[price] >= count for price, count in need_items)


def _combo_prices_from_cache_entry(combo):
    if isinstance(combo, dict):
        prices = combo.get('prices', [])
        if isinstance(prices, (list, tuple)):
            return [int(p) for p in prices if _safe_int(p, default=None, min_value=0) is not None]
        return []
    if isinstance(combo, (list, tuple)):
        return [int(p) for p in combo if _safe_int(p, default=None, min_value=0) is not None]
    return []


def _strip_combo_details_for_broad_cache(results):
    stripped_results = []
    for result in results or []:
        combos = result.get('combos', [])
        stripped_combos = []
        for combo in combos:
            prices = _combo_prices_from_cache_entry(combo)
            if prices:
                stripped_combos.append(prices)
        stripped_result = dict(result)
        stripped_result['combos'] = stripped_combos
        stripped_results.append(stripped_result)
    return stripped_results


def _extract_ocr_text_items(ocr_result):
    if ocr_result is None:
        return []
    if isinstance(ocr_result, tuple):
        if len(ocr_result) == 2 and isinstance(ocr_result[0], (list, tuple)):
            ocr_result = ocr_result[0]
        elif len(ocr_result) == 1:
            ocr_result = ocr_result[0]
    if not isinstance(ocr_result, (list, tuple)):
        ocr_result = [ocr_result]
    lines = []
    for item in ocr_result:
        text = ""
        score = None
        if isinstance(item, dict):
            text = item.get("text") or item.get("transcription") or ""
            score = item.get("score")
        elif isinstance(item, (list, tuple)):
            if len(item) >= 2 and isinstance(item[1], str):
                text = item[1]
            elif len(item) >= 1 and isinstance(item[0], str):
                text = item[0]
            if len(item) >= 3 and isinstance(item[2], (int, float)):
                score = item[2]
        elif isinstance(item, str):
            text = item
        if text and (score is None or score >= 0.2):
            lines.append(str(text))
    return lines


def _extract_number_from_priority_patterns(text, patterns):
    source = _normalize_ocr_text(text)
    for pattern in patterns:
        match = re.search(pattern, source)
        if not match:
            continue
        for group in match.groups():
            if group is not None:
                number = _parse_ocr_number(group)
                if number is not None:
                    return number
        number = _parse_ocr_number(match.group(0))
        if number is not None:
            return number
    return None


def get_ocr_engine():
    global OCR_ENGINE
    if OCR_ENGINE is not None:
        return OCR_ENGINE
    if RapidOCR is None:
        raise RuntimeError("未安装 rapidocr_onnxruntime，请先安装后再使用屏幕识别")
    with OCR_ENGINE_LOCK:
        if OCR_ENGINE is None:
            OCR_ENGINE = RapidOCR()
    return OCR_ENGINE


def run_rapidocr_on_image_path(image_path):
    engine = get_ocr_engine()
    ocr_result = engine(image_path)
    return _extract_ocr_text_items(ocr_result)


def extract_abc_fields_from_lines(lines):
    normalized = [_normalize_ocr_text(line) for line in lines if str(line).strip()]
    joined = "".join(normalized)
    sources = normalized + [joined]
    total_line = _pick_ocr_line(
        sources,
        include_all=("总件数",),
        include_any=("紫色", "金色", "红色"),
    )
    purple_line = _pick_ocr_line(
        sources,
        include_all=("紫色", "总数量"),
        exclude_any=("金色",),
    )
    gold_size_line = _pick_ocr_line(
        normalized,
        include_all=("金色", "所占格数"),
        exclude_any=("蓝色", "紫色", "红色", "总件数", "总数量", "平均价值"),
    )
    avg_line = _pick_ocr_line(
        sources,
        include_all=("金色", "平均价值"),
        exclude_any=("紫色",),
    )
    gold_count_line = _pick_ocr_line(
        sources,
        include_all=("金色", "总数量"),
        exclude_any=("蓝色", "紫色", "红色", "所占格", "平均价"),
    )
    total_items = _extract_number_after_keywords(total_line or joined, [
        "本局内紫色金色和红色品质藏品的总件数",
        "本局内所有紫色金色和红色品质藏品的总件数",
        "总件数",
    ])
    purple_count = _extract_number_after_keywords(purple_line or joined, [
        "本局内所有紫色藏品的总数量",
        "本局内所有紫色品质藏品的总数量",
        "所有紫色藏品的总数量",
        "所有紫色品质藏品的总数量",
        "紫色藏品的总数量",
        "紫色品质藏品的总数量",
    ])
    gold_total_size = _extract_number_from_priority_patterns(gold_size_line or "", [
        r"(?:本局内所有|所有|本局内)?金色品质藏品的所占格数(?:为|是|:|：)?\s*(\d[\d,]*)",
        r"(?:本局内所有|所有|本局内)?金色藏品的所占格数(?:为|是|:|：)?\s*(\d[\d,]*)",
        r"金色品质藏品的所占格数(?:为|是|:|：)?\s*(\d[\d,]*)",
        r"金色藏品的所占格数(?:为|是|:|：)?\s*(\d[\d,]*)",
    ]) or _extract_number_after_keywords(gold_size_line or "", [
        "本局内所有金色品质藏品的所占格数",
        "所有金色品质藏品的所占格数",
        "金色品质藏品的所占格数",
        "本局内所有金色藏品的所占格数",
        "所有金色藏品的所占格数",
        "金色藏品的所占格数",
    ])
    avg = _extract_number_after_keywords(avg_line or joined, [
        "本局内所有金色品质藏品的平均价值",
        "所有金色品质藏品的平均价值",
        "金色品质藏品的平均价值",
    ])

    gold_count = _extract_number_from_priority_patterns(gold_count_line or joined, [
        r"(?:本局内所有|所有|本局内)?金色品质藏品的总数量(?:为|是|:|：)?\s*(\d[\d,]*)",
        r"(?:本局内所有|所有|本局内)?金色藏品的总数量(?:为|是|:|：)?\s*(\d[\d,]*)",
        r"金色品质藏品的总数量(?:为|是|:|：)?\s*(\d[\d,]*)",
        r"金色藏品的总数量(?:为|是|:|：)?\s*(\d[\d,]*)",
    ]) or _extract_number_after_keywords(gold_count_line or joined, [
        "本局内所有金色藏品的总数量为",
        "本局内所有金色品质藏品的总数量为",
        "所有金色藏品的总数量为",
        "所有金色品质藏品的总数量为",
        "金色藏品的总数量为",
        "金色品质藏品的总数量为",
        "金色藏品总数量为",
        "金色总数量为",
    ])
    return {
        "total_items": total_items,
        "purple_count": purple_count,
        "gold_count": gold_count,
        "gold_total_size": gold_total_size,
        "avg": avg,
        "raw_lines": lines,
        "joined_text": joined,
    }


def capture_screen_and_ocr():
    if ImageGrab is None:
        raise RuntimeError("未安装 Pillow，无法截屏")
    try:
        image = ImageGrab.grab(all_screens=True)
    except Exception:
        image = ImageGrab.grab()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    try:
        image.save(tmp.name)
        lines = run_rapidocr_on_image_path(tmp.name)
        return extract_abc_fields_from_lines(lines)
    finally:
        tmp.close()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
# =================================================================

# ========================== 搜索缓存 ==========================
search_cache = {
    'target_avg': None,
    'double_gold': None,
    'total_items': None,
    'purple_count': None,
    'gold_results': None,
    'sizes': [],
    'timestamp': None
}
analysis_result_cache = {}
analysis_broad_cache = {}
cache_lock = threading.Lock()

combo_memo = {}
memo_lock = threading.Lock()
search_prefix_cache = {}
# =================================================================


def _complete_gold_sizes(gold_results):
    return [
        size for size in gold_results
        if isinstance(size, int) and not gold_results.get(f'{size}_truncated', False)
    ]


def build_prefix_tables(prices_sorted, max_n, max_repeat):
    m = len(prices_sorted)
    min_table = [[0] * (max_n + 1) for _ in range(m + 1)]
    max_table = [[0] * (max_n + 1) for _ in range(m + 1)]
    for i in range(m - 1, -1, -1):
        for need in range(1, max_n + 1):
            take = min(max_repeat, need)
            min_table[i][need] = take * prices_sorted[i] + min_table[i + 1][need - take]
            max_val = 0
            for k in range(max_repeat + 1):
                if k > need:
                    break
                val = k * prices_sorted[i] + max_table[i + 1][need - k]
                if val > max_val:
                    max_val = val
            max_table[i][need] = max_val
    return min_table, max_table


def get_gold_size(price):
    price = _safe_int(price, default=0, min_value=0) or 0
    original = price if price in PRICES_SET else price // 2
    return PRICE_TO_SIZE.get(original, 0)


def prune_and_search(prices_sorted, n, low, high, max_repeat, min_table, max_table,
                     start_idx=0, start_combo=None, start_sum=0, max_results=None, deadline=None):
    if n <= 0:
        return []
    m = len(prices_sorted)
    if start_idx > m or (start_combo and len(start_combo) > n):
        return []
    remaining_total = n - len(start_combo or [])
    if remaining_total < 0:
        return []
    if start_idx < m:
        if min_table[start_idx][remaining_total] + start_sum > high:
            return []
        if max_table[start_idx][remaining_total] + start_sum < low:
            return []

    results = []
    stop_flag = False
    yield_count = 0

    def backtrack(idx, current_sum, remaining, combo):
        nonlocal stop_flag, yield_count
        yield_count += 1
        if stop_flag:
            return
        if yield_count % 1000 == 0 and deadline and time.perf_counter() > deadline:
            stop_flag = True
            return
        if remaining == 0:
            if low <= current_sum <= high:
                results.append(list(combo))
                if max_results is not None and len(results) >= max_results:
                    stop_flag = True
            return
        if idx >= m:
            return
        if current_sum + min_table[idx][remaining] > high:
            return
        if current_sum + max_table[idx][remaining] < low:
            return
        p = prices_sorted[idx]
        max_take = min(max_repeat, remaining)
        for k in range(max_take + 1):
            if stop_flag:
                break
            nxt_remaining = remaining - k
            nxt_sum = current_sum + k * p
            if nxt_remaining > 0:
                if nxt_sum + min_table[idx + 1][nxt_remaining] > high:
                    continue
                if nxt_sum + max_table[idx + 1][nxt_remaining] < low:
                    continue
            combo.extend([p] * k)
            backtrack(idx + 1, nxt_sum, nxt_remaining, combo)
            for _ in range(k):
                combo.pop()

    combo = list(start_combo) if start_combo else []
    backtrack(start_idx, start_sum, remaining_total, combo)
    return results


def generate_subtasks(n, prices_sorted, low, high, max_repeat, min_table, max_table):
    m = len(prices_sorted)
    subtasks = []
    def enum(idx, current_sum, remaining, combo):
        if idx >= m or remaining == 0:
            return
        p = prices_sorted[idx]
        max_take = min(max_repeat, remaining)
        for k in range(max_take + 1):
            new_combo = combo + [p] * k
            new_sum = current_sum + k * p
            new_rem = remaining - k
            if new_rem == 0:
                subtasks.append((idx + 1, new_combo, new_sum))
            else:
                if len(new_combo) < 2:
                    enum(idx + 1, new_sum, new_rem, new_combo)
                else:
                    subtasks.append((idx + 1, new_combo, new_sum))
    enum(0, 0, n, [])
    return subtasks


def task_for_n(n, prices_sorted, max_repeat, min_table, max_table,
               start_idx=0, start_combo=[], start_sum=0, max_results=None, deadline=None,
               explicit_low=None, explicit_high=None):
    pid = os.getpid()
    start = time.perf_counter()
    if explicit_low is not None and explicit_high is not None:
        low = explicit_low
        high = explicit_high
    else:
        low = 0
        high = sum(prices_sorted)
    matches = prune_and_search(prices_sorted, n, low, high, max_repeat,
                               min_table, max_table, start_idx, start_combo, start_sum,
                               max_results=max_results, deadline=deadline)
    duration = time.perf_counter() - start
    return n, matches, duration, pid


def calculate_red_mean():
    weighted_sum = sum(p * w for p, w in zip(RED_PRICES, RED_WEIGHTS))
    total_weight = sum(RED_WEIGHTS)
    return weighted_sum / total_weight


def calculate_total_value(gold_count, gold_avg, red_count,
                          known_red_prices=None, known_gold_prices=None):
    return calculate_total_value_range(gold_count, gold_avg, red_count,
                                       known_red_prices or [])[1]


def convolve_pmfs(a, b):
    out = {}
    for x, pa in a.items():
        for y, pb in b.items():
            out[x + y] = out.get(x + y, 0.0) + pa * pb
    return out


def percentile_from_dist(dist, q):
    cum = 0.0
    for value in sorted(dist):
        cum += dist[value]
        if cum >= q - 1e-12:
            return value
    return max(dist)


_red_sum_cache = {}


def _sample_red_sum(pmf, k, n=8000, seed=20260818):
    rng = random.Random(seed)
    prices = sorted(pmf)
    weights = [pmf[p] for p in prices]
    dist = {}
    for _ in range(n):
        total = sum(rng.choices(prices, weights=weights, k=k))
        dist[total] = dist.get(total, 0) + 1
    return {total: count / n for total, count in dist.items()}


def get_red_sum_distributions(pmf, max_k):
    signature = tuple(round(pmf[p], 6) for p in sorted(pmf))
    entry = _red_sum_cache.get(signature)
    if entry is None:
        entry = {"dists": [None], "exact_upto": 0}
        _red_sum_cache[signature] = entry
    dists = entry["dists"]
    exact_upto = entry["exact_upto"]
    exact = dists[exact_upto] if exact_upto > 0 else None
    for k in range(len(dists), max_k + 1):
        if k <= RED_EXACT_LIMIT:
            if exact is None:
                exact = dict(pmf)
            else:
                exact = convolve_pmfs(exact, pmf)
            dists.append(exact)
            exact_upto = k
        else:
            dists.append(_sample_red_sum(pmf, k))
    entry["exact_upto"] = exact_upto
    return dists


def build_red_pmf(history=None, weights=None, prices=None):
    history = history if history is not None else load_history()
    weights = weights if weights is not None else RED_WEIGHTS
    prices = prices if prices is not None else RED_PRICES
    counts = Counter()
    for auction in history.get("auctions", []):
        for p in auction.get("prices", []):
            if p in prices:
                counts[p] += 1
    total = sum(counts.values())
    emp = {p: counts[p] / total for p in prices} if total else {}
    wsum = sum(weights)
    wpmf = {p: w / wsum for p, w in zip(prices, weights)} if wsum else {}
    if total < MIN_RED_SAMPLES or not emp:
        return wpmf
    if not wpmf:
        return emp
    return {p: RED_BLEND_WEIGHT * emp.get(p, 0.0) + (1 - RED_BLEND_WEIGHT) * wpmf[p] for p in prices}


def calculate_total_value_range(gold_count, gold_avg, red_count, known_red_prices=None, red_pmf=None):
    gold_total = gold_count * gold_avg
    known = sorted(
        p for p in (_safe_int(value, default=None, min_value=0) for value in (known_red_prices or []))
        if p is not None
    )
    known_count = len(known)
    if red_count <= known_count:
        red_sum = sum(known[:red_count])
        total = gold_total + red_sum
        return total, total, total
    known_sum = sum(known)
    unknown_count = red_count - known_count
    if red_pmf:
        dist = get_red_sum_distributions(red_pmf, unknown_count)[unknown_count]
        mean = sum(s * p for s, p in dist.items())
        low = percentile_from_dist(dist, 0.25)
        high = percentile_from_dist(dist, 0.75)
    else:
        low = unknown_count * UNKNOWN_RED_QUANTILES[0]
        mean = unknown_count * UNKNOWN_RED_QUANTILES[1]
        high = unknown_count * UNKNOWN_RED_QUANTILES[2]
    return gold_total + known_sum + low, gold_total + known_sum + mean, gold_total + known_sum + high


def _filter_cached_results(results, target_avg, total_items, purple_count,
                           known_gold_prices, known_red_prices, unknown_red_count,
                           gold_total_size, required_sizes):
    filtered_results = []
    required_set = set(required_sizes or [])
    min_gold = max(1, len(known_gold_prices))
    min_red = len(known_red_prices) + unknown_red_count
    known_gold_need = tuple(sorted(Counter(known_gold_prices).items())) if known_gold_prices else ()
    red_pmf = build_red_pmf(load_history(), RED_WEIGHTS, RED_PRICES)

    for result in results:
        gold_count = result.get('gold_count')
        if gold_count is None or (required_set and gold_count not in required_set):
            continue
        if gold_count < min_gold:
            continue

        is_estimated = bool(result.get('is_estimated'))
        if total_items is not None:
            red_count = total_items - purple_count - gold_count
        else:
            red_count = result.get('red_count')
        if red_count is None:
            red_count = result.get('red_count', 0)

        if red_count < min_red:
            continue

        if is_estimated:
            low_value, mid_value, high_value = calculate_total_value_range(
                gold_count, target_avg, red_count, known_red_prices, red_pmf
            )
            filtered_results.append({
                'gold_count': gold_count,
                'red_count': red_count,
                'total_value': round(mid_value),
                'low_value': round(low_value),
                'high_value': round(high_value),
                'is_estimated': True,
                'combo_count': 0,
                'has_details': True,
                'combos': [],
                'is_truncated': False
            })
            continue

        combos = result.get('combos', [])
        filtered_combos = combos
        if known_gold_need:
            filtered_combos = [
                combo for combo in filtered_combos
                if _combo_covers_cached(tuple(_combo_prices_from_cache_entry(combo)), known_gold_need)
            ]
        if gold_total_size:
            size_filtered = []
            for combo in filtered_combos:
                combo_prices = tuple(_combo_prices_from_cache_entry(combo))
                _, total_size = _gold_combo_size_info(combo_prices)
                if total_size == gold_total_size:
                    size_filtered.append(combo)
            filtered_combos = size_filtered

        if not filtered_combos:
            continue

        low_value, mid_value, high_value = calculate_total_value_range(
            gold_count, target_avg, red_count, known_red_prices, red_pmf
        )

        combos_with_sizes = []
        for combo in filtered_combos[:DISPLAY_COMBOS]:
            combo_prices = tuple(_combo_prices_from_cache_entry(combo))
            sizes_list, total_size = _gold_combo_size_info(combo_prices)
            size_str = '+'.join(str(s) for s in sizes_list)
            combos_with_sizes.append({
                'prices': list(combo_prices),
                'sizes': sizes_list,
                'size_str': size_str,
                'total_size': total_size
            })

        filtered_results.append({
            'gold_count': gold_count,
            'red_count': red_count,
            'total_value': round(mid_value),
            'low_value': round(low_value),
            'high_value': round(high_value),
            'is_estimated': False,
            'combo_count': len(filtered_combos),
            'has_details': len(filtered_combos) > 0,
            'combos': combos_with_sizes,
            'is_truncated': result.get('is_truncated', False)
        })

    filtered_results.sort(key=lambda x: x['gold_count'])
    return filtered_results


def search_all_gold_combinations(target_avg, sizes, deadline, double_gold=False, allow_truncation=True):
    gold_results = {}
    for n in sizes:
        if n > MAX_SEARCH_SIZE:
            gold_results[n] = []
    max_n = max(sizes) if sizes else 1
    
    search_prices = sorted([p * 2 if double_gold else p for p in PRICES])
    prefix_key = (bool(double_gold), max_n)
    if prefix_key not in search_prefix_cache:
        search_prefix_cache[prefix_key] = build_prefix_tables(search_prices, max_n, MAX_REPEAT)
    search_min_table, search_max_table = search_prefix_cache[prefix_key]
    
    for n in sizes:
        if time.perf_counter() > deadline:
            gold_results['timeout'] = True
            break
        
        memo_key = (round(target_avg, 2), n, double_gold, allow_truncation)
        with memo_lock:
            memo_entry = combo_memo.get(memo_key)
            if memo_entry is not None:
                cached_combos, cached_truncated = memo_entry
                gold_results[n] = cached_combos
                if cached_truncated:
                    gold_results[f'{n}_truncated'] = True
                continue
        
        target_low = n * (target_avg - ERROR_MARGIN)
        target_high = n * (target_avg + ERROR_MARGIN)
        
        low = math.floor(target_low)
        high = math.ceil(target_high)
        
        if n <= MAX_SEARCH_SIZE:
            unique_matches = []
            truncated = False
            max_results = None if not allow_truncation else MAX_COMBOS_PER_N + 1
            matches = prune_and_search(
                search_prices, n, low, high,
                MAX_REPEAT, search_min_table, search_max_table,
                0, [], 0, max_results=max_results, deadline=deadline
            )
            
            if allow_truncation:
                for combo in matches:
                    unique_matches.append(combo)
                    if len(unique_matches) >= MAX_COMBOS_PER_N:
                        truncated = True
                        break
            else:
                unique_matches = list(matches)

            if unique_matches:
                full_combos = []
                limit = MAX_COMBOS_PER_N if allow_truncation else len(unique_matches)
                for combo in unique_matches[:limit]:
                    original_combo = []
                    for p in combo:
                        try:
                            p_int = int(p)
                        except (TypeError, ValueError):
                            continue
                        original_combo.append(p_int // 2 if double_gold else p_int)
                    full_combos.append(sorted(original_combo))
                gold_results[n] = full_combos
                if truncated:
                    gold_results[f'{n}_truncated'] = True
        else:
            prices_list = sorted([p * 2 if double_gold else p for p in PRICES])
            if len(prices_list) >= n:
                min_possible = sum(prices_list[:n])
                max_possible = sum(prices_list[-n:])
                if not (max_possible < target_low or min_possible > target_high):
                    gold_results[n] = []

        with memo_lock:
            combo_memo[memo_key] = (
                gold_results.get(n, []),
                bool(gold_results.get(f'{n}_truncated', False)),
            )

    gold_results['timeout'] = time.perf_counter() > deadline
    return gold_results


# ========================== Flask路由 ==========================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/assets/<asset_name>.png', methods=['GET'])
def asset_image(asset_name):
    mapping = {
        'app-icon': APP_ICON_CANDIDATES,
        'badge': DECORATIVE_BADGE_CANDIDATES,
        'banner': BANNER_CANDIDATES,
    }
    path = _first_existing_path(mapping.get(asset_name, []))
    if not path:
        abort(404)
    return send_file(path, mimetype='image/png', conditional=False, max_age=0)


@app.route('/api/prices', methods=['GET'])
def get_prices():
    return jsonify({
        'gold_prices': PRICES,
        'gold_sizes': GOLD_SIZES,
        'red_prices': RED_PRICES,
        'red_sizes': RED_SIZES_FILTERED,
        'has_unknown': True
    })


@app.route('/api/ocr/screen', methods=['POST'])
def ocr_screen():
    tmp_path = None
    try:
        image_file = request.files.get("image")
        if image_file is None:
            return jsonify({"error": "未收到截图文件"}), 400
        if request.content_length and request.content_length > MAX_OCR_UPLOAD_BYTES:
            return jsonify({"error": "截图文件过大"}), 413
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp_path = tmp.name
            image_file.save(tmp_path)
        lines = run_rapidocr_on_image_path(tmp_path)
        fields = extract_abc_fields_from_lines(lines)
        return jsonify({
            "success": True,
            "fields": fields,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@app.route('/api/analyze', methods=['POST'])
def analyze():
    global search_cache
    global analysis_result_cache
    global analysis_broad_cache
    
    try:
        data = request.get_json(silent=True) or {}
        target_avg = float(data.get('avg') or 0)
        if target_avg <= 0:
            return jsonify({'error': '金色均价必须大于 0'}), 400

        total_items = _safe_int(data.get('total_items'), default=None, min_value=1, max_value=50)
        purple_count = _safe_int(data.get('purple_count'), default=0, min_value=0, max_value=40) or 0
        search_timeout = float(data.get('search_timeout') or 20)
        search_timeout = max(1.0, min(search_timeout, MAX_SEARCH_TIMEOUT))
        double_gold = bool(data.get('double_gold', False))
        gold_total_size = _safe_int(data.get('gold_total_size'), default=None, min_value=1)

        known_gold_prices = _parse_int_list(data.get('gold_prices', []), min_value=0, max_items=MAX_PRICE_LIST_ITEMS)
        known_red_prices, unknown_red_count = _parse_red_prices(data.get('red_prices', []))
        known_red_count = _safe_int(data.get('known_red_count'), default=0, min_value=0) or 0
        known_gold_count = _safe_int(data.get('known_gold_count'), default=0, min_value=0) or 0
        known_gold_count_from_ocr = bool(data.get('known_gold_count_from_ocr', False))
        min_gold_count = _safe_int(data.get('min_gold'), default=0, min_value=0) or 0
        min_red_count = _safe_int(data.get('min_red'), default=0, min_value=0) or 0

        if gold_total_size is not None and gold_total_size <= 0:
            gold_total_size = None

        known_gold_prices = [_safe_int(p, default=0, min_value=0) for p in known_gold_prices if _safe_int(p, default=None, min_value=0) is not None]
        known_red_prices = [_safe_int(p, default=0, min_value=0) for p in known_red_prices if _safe_int(p, default=None, min_value=0) is not None]
        
        if double_gold and known_gold_prices:
            processed_gold_prices = []
            for p in known_gold_prices:
                p_int = _safe_int(p, default=None, min_value=0)
                if p_int is None:
                    continue
                if p_int in PRICES:
                    processed_gold_prices.append(p_int)
                else:
                    processed_gold_prices.append(p_int // 2)
            known_gold_prices = processed_gold_prices
        
        min_red_from_prices = len(known_red_prices) + unknown_red_count
        min_red = max(min_red_count, min_red_from_prices)
        min_gold = max(min_gold_count, len(known_gold_prices))
        final_cache_key = (
            round(target_avg, 2),
            bool(double_gold),
            total_items,
            purple_count,
            gold_total_size,
            tuple(sorted(known_gold_prices)),
            tuple(sorted(known_red_prices)),
            unknown_red_count,
            known_gold_count,
            known_red_count,
        )

        with cache_lock:
            cached_payload = analysis_result_cache.get(final_cache_key)
        if cached_payload is not None:
            if len(cached_payload) == 6:
                results, red_mean, unknown_red_mean, cached_total, cached_timeout, cached_warning = cached_payload
            else:
                results, red_mean, unknown_red_mean, cached_total, cached_timeout = cached_payload
                cached_warning = None
            return jsonify({
                'results': results,
                'red_mean': red_mean,
                'unknown_red_mean': unknown_red_mean,
                'total': cached_total,
                'double_gold': double_gold,
                'unknown_red_count': unknown_red_count,
                'gold_total_size': gold_total_size,
                'cached': True,
                'timeout': cached_timeout,
                'warning': cached_warning
            })
        
        # ========== 已知件数处理（新增） ==========
        if known_gold_count > 0:
            # 用户已知金色件数，直接使用
            required_sizes = [known_gold_count]
        elif known_red_count > 0 and total_items:
            # 用户已知红色件数，金色 = 总 - 紫 - 红
            gold_count = total_items - purple_count - known_red_count
            required_sizes = [gold_count] if gold_count > 0 else []
        elif total_items:
            max_gold = total_items - purple_count
            required_sizes = list(range(max(1, min_gold), max_gold + 1)) if max_gold > 0 else []
        else:
            max_list = (total_items - purple_count) if total_items else MAX_LIST_SIZE
            required_sizes = list(range(max(1, min_gold), max_list + 1))

        broad_cache_key = (
            round(target_avg, 2),
            bool(double_gold),
            total_items,
            purple_count,
        )
        with cache_lock:
            cached_broad = analysis_broad_cache.get(broad_cache_key)
        if cached_broad is not None:
            broad_results, broad_timeout = cached_broad
            filtered_results = _filter_cached_results(
                broad_results,
                target_avg,
                total_items,
                purple_count,
                known_gold_prices,
                known_red_prices,
                unknown_red_count,
                gold_total_size,
                required_sizes,
            )
            red_mean = calculate_red_mean()
            payload = {
                'results': filtered_results,
                'red_mean': round(red_mean),
                'unknown_red_mean': round(sum(p * w for p, w in build_red_pmf(load_history(), RED_WEIGHTS, RED_PRICES).items())) if RED_PRICES else 0,
                'total': len(filtered_results),
                'double_gold': double_gold,
                'unknown_red_count': unknown_red_count,
                'gold_total_size': gold_total_size,
                'cached': True,
                'timeout': broad_timeout
                }
            if known_red_prices:
                history = load_history()
                auctions = history.get("auctions", [])
                recently_saved = set()
                for auction in reversed(auctions):
                    if auction.get("source") == "auto_from_analysis":
                        recently_saved.update(auction.get("prices", []))
                        break
                new_prices = [p for p in known_red_prices if p not in recently_saved]
                if new_prices:
                    history["auctions"].append({
                        "prices": new_prices,
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "auto_from_analysis"
                    })
                    save_history(history)
            return jsonify(payload)
        
        cache_key = (target_avg, double_gold, total_items, purple_count)
        
        use_cache = False
        gold_results = None

        cached_results = None
        cached_sizes = set()
        with cache_lock:
            cached_key = (
                search_cache.get('target_avg'),
                search_cache.get('double_gold'),
                search_cache.get('total_items'),
                search_cache.get('purple_count')
            )
            if cached_key == cache_key and search_cache.get('gold_results') is not None:
                cached_results = search_cache['gold_results']
                cached_sizes = set(search_cache.get('sizes', []))

        if cached_results is not None:
            missing = [s for s in required_sizes if s not in cached_sizes]
            use_cache = True
            gold_results = {k: v for k, v in cached_results.items() if isinstance(k, int) and k in required_sizes}
            if missing:
                deadline = time.perf_counter() + search_timeout
                new_results = search_all_gold_combinations(
                    target_avg, missing, deadline, double_gold, allow_truncation=not known_gold_prices
                )
                gold_results.update(new_results)
                complete_new_sizes = [
                    size for size in missing
                    if isinstance(size, int) and size in new_results and not new_results.get(f'{size}_truncated', False)
                ]
                if complete_new_sizes and not known_gold_prices:
                    with cache_lock:
                        merged_results = dict(cached_results)
                        for size in complete_new_sizes:
                            merged_results[size] = new_results[size]
                        search_cache['target_avg'] = target_avg
                        search_cache['double_gold'] = double_gold
                        search_cache['total_items'] = total_items
                        search_cache['purple_count'] = purple_count
                        search_cache['gold_results'] = merged_results
                        search_cache['sizes'] = sorted(cached_sizes.union(complete_new_sizes))
                        search_cache['timestamp'] = time.time()
        
        if not use_cache:
            deadline = time.perf_counter() + search_timeout
            gold_results = search_all_gold_combinations(
                target_avg, required_sizes, deadline, double_gold, allow_truncation=not known_gold_prices
            )
            complete_sizes = _complete_gold_sizes(gold_results)
            if complete_sizes and not known_gold_prices:
                with cache_lock:
                    search_cache['target_avg'] = target_avg
                    search_cache['double_gold'] = double_gold
                    search_cache['total_items'] = total_items
                    search_cache['purple_count'] = purple_count
                    search_cache['gold_results'] = {size: gold_results[size] for size in complete_sizes}
                    search_cache['sizes'] = complete_sizes
                    search_cache['timestamp'] = time.time()
        
        results = []
        broad_results = []
        known_gold_counter = Counter(known_gold_prices)
        red_pmf = build_red_pmf(load_history(), RED_WEIGHTS, RED_PRICES)
        warning_message = None
        
        for gold_count in required_sizes:
            if total_items:
                red_count = total_items - purple_count - gold_count
            else:
                red_count = known_red_count if known_red_count > 0 else min_red

            if gold_count > MAX_SEARCH_SIZE:
                if red_count < min_red:
                    continue
                low_value, mid_value, high_value = calculate_total_value_range(
                    gold_count, target_avg, red_count,
                    known_red_prices, red_pmf
                )
                estimated_result = {
                    'gold_count': gold_count,
                    'red_count': red_count,
                    'total_value': round(mid_value),
                    'low_value': round(low_value),
                    'high_value': round(high_value),
                    'is_estimated': True,
                    'combo_count': 0,
                    'has_details': True,
                    'combos': [],
                    'is_truncated': False
                }
                results.append(estimated_result)
                broad_results.append(dict(estimated_result))
                continue

            if red_count < min_red:
                continue

            if gold_count not in gold_results:
                continue

            combos = gold_results.get(gold_count, [])
            is_truncated = gold_results.get(f'{gold_count}_truncated', False)
            
            filtered_combos = combos
            if known_gold_counter:
                known_gold_need = tuple(sorted(known_gold_counter.items()))
                filtered_combos = []
                for combo in combos:
                    if _combo_covers_cached(tuple(combo), known_gold_need):
                        filtered_combos.append(combo)
            
            if gold_total_size:
                size_filtered = []
                for combo in filtered_combos:
                    _, total_size = _gold_combo_size_info(tuple(combo))
                    if total_size == gold_total_size:
                        size_filtered.append(combo)
                filtered_combos = size_filtered
            
            if not filtered_combos:
                continue
            
            low_value, mid_value, high_value = calculate_total_value_range(
                gold_count, target_avg, red_count,
                known_red_prices, red_pmf
            )
            
            combos_with_sizes = []
            for combo in filtered_combos[:DISPLAY_COMBOS]:
                sizes_list, total_size = _gold_combo_size_info(tuple(combo))
                size_str = '+'.join(str(s) for s in sizes_list)
                combos_with_sizes.append({
                    'prices': combo,
                    'sizes': sizes_list,
                    'size_str': size_str,
                    'total_size': total_size
                })
            
            exact_result = {
                'gold_count': gold_count,
                'red_count': red_count,
                'total_value': round(mid_value),
                'low_value': round(low_value),
                'high_value': round(high_value),
                'is_estimated': False,
                'combo_count': len(filtered_combos),
                'has_details': len(filtered_combos) > 0,
                'combos': combos_with_sizes,
                'is_truncated': is_truncated
            }
            results.append(exact_result)
            broad_results.append({
                'gold_count': gold_count,
                'red_count': red_count,
                'total_value': round(mid_value),
                'low_value': round(low_value),
                'high_value': round(high_value),
                'is_estimated': False,
                'combo_count': len(filtered_combos),
                'has_details': len(filtered_combos) > 0,
                'combos': [list(combo) for combo in filtered_combos],
                'is_truncated': is_truncated
            })
        
        results.sort(key=lambda x: x['gold_count'])
        if known_gold_prices:
            truncated_exact_sizes = [
                size for size in required_sizes
                if isinstance(size, int)
                and size <= MAX_SEARCH_SIZE
                and gold_results.get(f'{size}_truncated', False)
            ]
            if truncated_exact_sizes:
                warning_message = '包含该金价的组合可能因截断而未显示'
        if (
            not gold_total_size
            and not known_gold_prices
            and not known_red_prices
            and unknown_red_count == 0
            and known_gold_count == 0
            and known_red_count == 0
            and not gold_results.get('timeout', False)
        ):
            with cache_lock:
                analysis_broad_cache[broad_cache_key] = (broad_results, False)
        red_mean = calculate_red_mean()
        
        if known_red_prices:
            history = load_history()
            auctions = history.get("auctions", [])
            recently_saved = set()
            for auction in reversed(auctions):
                if auction.get("source") == "auto_from_analysis":
                    recently_saved.update(auction.get("prices", []))
                    break
            new_prices = [p for p in known_red_prices if p not in recently_saved]
            if new_prices:
                history["auctions"].append({
                    "prices": new_prices,
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "auto_from_analysis"
                })
                save_history(history)
        
        payload = {
            'results': results,
            'red_mean': round(red_mean),
            'unknown_red_mean': round(sum(p * w for p, w in red_pmf.items())) if red_pmf else 0,
            'total': len(results),
            'double_gold': double_gold,
            'unknown_red_count': unknown_red_count,
            'gold_total_size': gold_total_size,
            'cached': use_cache,
            'timeout': gold_results.get('timeout', False),
            'warning': warning_message
        }
        if not gold_results.get('timeout', False):
            with cache_lock:
                analysis_result_cache[final_cache_key] = (
                    results,
                    payload['red_mean'],
                    payload['unknown_red_mean'],
                    payload['total'],
                    payload['timeout'],
                    payload['warning'],
                )
        return jsonify(payload)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'results': [],
            'red_mean': 0,
            'total': 0,
            'double_gold': False,
            'unknown_red_count': 0,
            'gold_total_size': None,
            'cached': False
        }), 500


@app.route('/api/memory', methods=['GET'])
def get_memory():
    history = load_history()
    auctions = history.get("auctions", [])
    price_counts = Counter()
    for auction in auctions:
        for p in auction.get("prices", []):
            price_counts[p] += 1
    return jsonify({
        'auctions': auctions,
        'price_counts': dict(sorted(price_counts.items())),
        'total_auctions': len(auctions)
    })


@app.route('/api/memory/add', methods=['POST'])
def add_memory():
    data = request.get_json(silent=True) or {}
    try:
        prices = _parse_int_list(data.get('prices', []), min_value=0, max_items=MAX_PRICE_LIST_ITEMS)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if not prices:
        return jsonify({'error': '未输入有效价格'}), 400
    history = load_history()
    history["auctions"].append({
        "prices": prices,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_history(history)
    return jsonify({'success': True, 'prices': prices})


@app.route('/api/memory/delete/<int:idx>', methods=['DELETE'])
def delete_memory(idx):
    history = load_history()
    auctions = history.get("auctions", [])
    if 0 <= idx < len(auctions):
        removed = auctions.pop(idx)
        history["auctions"] = auctions
        save_history(history)
        return jsonify({'success': True, 'removed': removed})
    return jsonify({'error': '无效索引'}), 400


@app.route('/api/memory/edit/<int:idx>', methods=['PUT'])
def edit_memory(idx):
    history = load_history()
    auctions = history.get("auctions", [])
    if 0 <= idx < len(auctions):
        data = request.get_json(silent=True) or {}
        try:
            prices = _parse_int_list(data.get('prices', []), min_value=0, max_items=MAX_PRICE_LIST_ITEMS)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        if prices:
            auctions[idx]["prices"] = prices
            auctions[idx]["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            history["auctions"] = auctions
            save_history(history)
            return jsonify({'success': True, 'prices': prices})
    return jsonify({'error': '无效索引'}), 400


@app.route('/api/weights/update', methods=['POST'])
def update_weights():
    global RED_WEIGHTS
    
    history = load_history()
    auctions = history.get("auctions", [])
    if not auctions:
        return jsonify({'error': '记忆池为空'}), 400
    
    new_weights = DEFAULT_RED_WEIGHTS.copy()
    
    price_counts = Counter()
    total = 0
    for auction in auctions:
        for p in auction.get("prices", []):
            price_counts[p] += 1
            total += 1
    
    for price, count in price_counts.items():
        if price in RED_PRICES:
            idx = RED_PRICES.index(price)
            boost = 1.0 + min(count / total * 5, 3.0)
            new_weights[idx] *= boost
    
    RED_WEIGHTS = new_weights
    save_red_weights(RED_WEIGHTS)
    
    return jsonify({'success': True, 'red_mean': round(calculate_red_mean())})


@app.route('/api/toggle_on_top', methods=['POST'])
def toggle_on_top():
    try:
        import builtins
        toggle_func = getattr(builtins, 'toggle_top_in_process', None)
        if toggle_func:
            result = toggle_func()
            return jsonify({'success': True, 'on_top': result})
        return jsonify({'success': False, 'error': '置顶函数不可用'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)

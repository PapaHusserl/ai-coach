"""Проверка 8. Структура ручного экспорта Garmin (zip): сон, HRV, FIT активностей.

Запуск: ! uv run python -I spikes/garmin/export_zip.py /путь/к/export.zip
Читает zip в памяти, ничего не распаковывает и не пишет. Печатает только счётчики,
имена файлов (длинные числа заменены на #) и имена ключей JSON, без значений.
Вложенные zip (UploadedFiles_*.zip с FIT) смотрит на один уровень вглубь.
"""

import argparse
import io
import json
import re
import zipfile
from collections import Counter

MAX_JSON = 50_000_000


def mask(name: str) -> str:
    return re.sub(r"\d{6,}", "#", name)


def json_shape(data: object) -> str:
    if isinstance(data, list):
        first = data[0] if data else None
        keys = sorted(first) if isinstance(first, dict) else type(first).__name__
        return f"list[{len(data)}], ключи элемента: {keys}"
    if isinstance(data, dict):
        return f"dict, ключи: {sorted(data)}"
    return type(data).__name__


def scan(zf: zipfile.ZipFile, prefix: str, found: dict[str, list[str]]) -> None:
    for info in zf.infolist():
        if info.is_dir():
            continue
        low = info.filename.lower()
        shown = prefix + mask(info.filename)
        if low.endswith(".zip") and not prefix:
            with zipfile.ZipFile(io.BytesIO(zf.read(info))) as inner:
                scan(inner, f"{shown} > ", found)
        elif low.endswith(".fit"):
            found["fit"].append(shown)
        elif "sleep" in low:
            found["sleep"].append(shown)
        elif "hrv" in low or "healthstatus" in low:
            found["hrv"].append(shown)


def print_json_shapes(zf: zipfile.ZipFile) -> None:
    print("\n== структура JSON (до 6 файлов сна/HRV верхнего уровня)")
    shown_count = 0
    for info in zf.infolist():
        low = info.filename.lower()
        is_target = ("sleep" in low or "hrv" in low) and low.endswith(".json")
        if is_target and info.file_size < MAX_JSON and shown_count < 6:
            print(f"  {mask(info.filename)}: {json_shape(json.loads(zf.read(info)))}")
            shown_count += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path")
    args = parser.parse_args()
    found: dict[str, list[str]] = {"sleep": [], "hrv": [], "fit": []}
    with zipfile.ZipFile(args.zip_path) as zf:
        names = [i.filename for i in zf.infolist() if not i.is_dir()]
        print(f"Файлов в архиве: {len(names)}")
        print("Расширения:", dict(Counter(n.rsplit(".", 1)[-1].lower() for n in names)))
        print("Верхние каталоги:", dict(Counter(n.split("/")[0] for n in names)))
        scan(zf, "", found)
        for kind, files in found.items():
            print(f"\n== {kind}: файлов {len(files)}")
            for shown in files[:10]:
                print("  ", shown)
        print_json_shapes(zf)


main()

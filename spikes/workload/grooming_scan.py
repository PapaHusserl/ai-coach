"""Спайк: ~/bin/hb-watch/{done,pending} и log.txt (только чтение, без имён файлов)."""

import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from common import save_json, say

ROOT = Path.home() / "bin" / "hb-watch"


def scan(name: str) -> list[dict]:
    rows = []
    for p in sorted((ROOT / name).iterdir()):
        if not p.is_file():
            continue
        st = p.stat()
        text = p.read_text(encoding="utf-8", errors="replace")
        rows.append({
            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "size": st.st_size,
            "has_pr": bool(re.search(r"^pr:\s*\S", text, re.M)),
            "has_commit": bool(re.search(r"^commit:\s*\S", text, re.M)),
        })
    return rows


def main() -> None:
    result = {}
    for name in ("done", "pending"):
        rows = scan(name)
        result[name] = rows
        days = Counter(r["mtime"][:10] for r in rows)
        say(f"{name}/: файлов {len(rows)}; с pr: {sum(r['has_pr'] for r in rows)}; "
            f"с commit: {sum(r['has_commit'] for r in rows)}")
        say(f"{name}/ по дням mtime: {dict(sorted(days.items()))}")
    lines = (ROOT / "log.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [int(m.group(1)) for ln in lines if (m := re.search(r"ok, hits: (\d+)", ln))]
    new = [int(m.group(1)) for ln in lines if (m := re.search(r"ok, new: (\d+)", ln))]
    kinds = Counter("init" if ln.endswith("init") else "ok_hits" if "ok, hits" in ln
                    else "ok_new" if "ok, new" in ln else "other" for ln in lines)
    say(f"log.txt: строк {len(lines)}; виды: {dict(kinds)}; сумма hits: {sum(hits)}; "
        f"максимум hits: {max(hits, default=0)}")
    say(f"log.txt 'ok, new: N, pending: M': строк {len(new)}; сумма new: {sum(new)}; строк с new>0: {sum(1 for n in new if n)}")
    say("форма строки лога: '<дата русской локали> (+TZ) <init | ok, hits: N | ok, new: N, pending: M>'")
    say(f"сверка: файлов done+pending = {len(result['done']) + len(result['pending'])}; "
        f"сумма hits в логе = {sum(hits)}")
    save_json("grooming_shape.json", result)


if __name__ == "__main__":
    main()

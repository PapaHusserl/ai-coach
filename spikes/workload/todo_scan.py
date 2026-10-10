"""Спайк: форма ~/.claude/todo.json (только чтение). Названия и заметки в вывод не попадают."""

import json
from collections import Counter
from pathlib import Path

from common import save_json, say

TODO = Path.home() / ".claude" / "todo.json"


def main() -> None:
    raw = TODO.read_bytes()
    data = json.loads(raw)
    say(f"размер файла: {len(raw)} байт; тип корня: {type(data).__name__}; записей: {len(data)}")
    say(f"ключи (в скольких записях): {dict(Counter(k for r in data for k in r))}")
    say(f"состояния: {dict(Counter(r.get('state') for r in data))}")
    say(f"уникальных id: {len({r.get('id') for r in data})}; без пропусков 1..N: "
        f"{sorted(r.get('id') for r in data) == list(range(1, len(data) + 1))}")
    say(f"подзадач (заголовок с '↳'): {sum(1 for r in data if str(r.get('title', '')).startswith('↳'))}")
    by_state = Counter((r.get("state"), r.get("created") == r.get("updated")) for r in data)
    say("состояние x (updated vs created): " + ", ".join(
        f"{s}/{'=' if e else '>'}: {n}" for (s, e), n in sorted(by_state.items(), key=str)))
    closed = [r for r in data if r.get("state") in ("done", "dropped")]
    say(f"закрытых (done/dropped): {len(closed)}; по дню updated: "
        f"{dict(sorted(Counter(r.get('updated') for r in closed).items()))}")
    opened = [r for r in data if r.get("state") not in ("done", "dropped")]
    say(f"открытых: {len(opened)}; по дню created: "
        f"{dict(sorted(Counter(r.get('created') for r in opened).items()))}")
    save_json("todo_shape.json", [
        {"id": r.get("id"), "state": r.get("state"), "created": r.get("created"),
         "updated": r.get("updated"), "sub": str(r.get("title", "")).startswith("↳")}
        for r in data])
    say("гипотеза 'updated меняется при правке текста': сними todo_shape.json до и после правки "
        "текста открытой задачи (скрипт перезапишет файл - скопируй предыдущий) и сравни updated")


if __name__ == "__main__":
    main()

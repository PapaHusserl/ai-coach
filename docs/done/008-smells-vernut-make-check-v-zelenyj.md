# 8. Smells: вернуть `make check` в зелёный

status: done
priority: medium
updated: 2026-10-28

`make smells` красный и на HEAD 401c68b: порог 0, находок 4 — `cli/main.py` (сложность файла 54), `mcp_server/tools.py`
(51), `sync/workload_sync.py: sync_workload` (19), `workload/config.py: _title_rules` (19). Найдено в шаге 24 партии 5
(docs/plan-24-micronutrients.md, «Правки по ревью» п. 13); решение Влада 2026-10-27 — отдельным шагом.

## Закрыто

Шаг 25, 2026-10-28 — [plan-25-smells.md](../plan-25-smells.md).

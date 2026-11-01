# 36. workload в сводке у своего лимита
status: done
priority: low
updated: 2026-11-01

`workload` в сводке 3 968 / 4 000 Б (`SNAPSHOT_CHARS`) на 7 днях: ещё один счётчик (`screen_*`, `demand`)
начнёт молча резать дни — компактная проекция полей (как `AGENDA_FIELDS`) или свой лимит. Источник —
docs/plan-n12.md «Побочные находки» 1.

## Закрыто

Шаг Н5, 2026-11-01 — [plan-n5.md](../plan-n5.md): свой лимит `WORKLOAD_CHARS = 5000` для `workload` в сводке (Р14).

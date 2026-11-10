# 70. Тест списка событий зависит от сегодняшней даты
status: done
priority: high
updated: 2026-11-11

`tests/test_cli_agenda.py::test_list_shows_events_with_ids_and_statuses` красный с 2026-11-10: событие из
`coach_event` (`tests/workload_fakes.py:112`, дата 2026-10-10) вышло из окна `coach event list` «30 дней назад»
(`cli/agenda.py:78`, `date.today()`). Найдено полным прогоном перед коммитом партии 2 П4 (Python в партии не менялся).
Нужно зафиксировать «сегодня» в тесте или передать `--from`.

## Закрыто

Шаг Н27, 2026-11-11 — [plan-n27.md](../plan-n27.md).

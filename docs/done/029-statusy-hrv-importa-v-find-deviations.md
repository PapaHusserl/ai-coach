# 29. Статусы HRV импорта в find_deviations
status: done
priority: low
updated: 2026-11-01

`BAD_HRV_STATUSES = ("LOW", "UNBALANCED")` не знает статусов импорта (IN_RANGE/BELOW/ABOVE): плохой HRV
импортных строк до 2026-09-30 (BELOW — 19 строк) отклонением не считается. Источник — docs/plan-n11.md
«Побочные находки» 1.

## Закрыто

Шаг Н16, 2026-11-01 — [plan-n16.md](../plan-n16.md): BELOW добавлен в `BAD_HRV_STATUSES` и считается как LOW (Р1).

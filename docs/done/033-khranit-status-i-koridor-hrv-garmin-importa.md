# 33. Хранить статус и коридор HRV Garmin импорта
status: done
priority: low
updated: 2026-11-01

`export_days.add_hrv` не пишет `hrv_weekly_avg` и `hrv_status` импорта; коридор Garmin
(`hrvSummary.baseline`, границы) не хранится — источник для сверки своего коридора в v2.9.
Источник — docs/plan-n11.md «Побочные находки» 5.

## Закрыто

Шаг Н16, 2026-11-01 — [plan-n16.md](../plan-n16.md): `list_hrv_corridor` читает коридор API и импорта из
`raw_json`, миграции нет (Р3). Уточнение: `add_hrv` пишет `hrv_status` импорта, текст пункта в этом неверен
(«Побочные находки» 1 плана).

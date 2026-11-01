# 30. last_rest_hr не видит пульс покоя импорта
status: done
priority: medium
updated: 2026-11-01

`store/garmin_data.py last_rest_hr` читает только `$.sleep.restingHeartRate` (API): для дат до 2026-10-01
`get_load` отвечает «нет свежего пульса покоя», хотя он есть в `$.hrv.metrics[type=HR]`. Мешает анализу
истории (Н6, Н9). Источник — docs/plan-n11.md «Побочные находки» 2.

## Закрыто

Шаг Н16, 2026-11-01 — [plan-n16.md](../plan-n16.md): `last_rest_hr` и `list_recovery_days` берут HR импорта, если
`restingHeartRate` API нет (Р2).

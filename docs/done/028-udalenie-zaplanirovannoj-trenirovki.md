# 28. Удаление запланированной тренировки
status: done
priority: medium
updated: 2026-11-02

Влад хочет удалять запланированную тренировку. Сейчас в CLI есть только approve/push/link; в MCP —
cancel_draft_workout, и только для черновиков. Открыто для архитектора: какие статусы удаляются
(draft, approved, pushed), удалять ли строку или ставить cancelled, снимать ли с календаря Garmin
у pushed (remove_old в plan/service.py это уже умеет) и с подтверждением y/N; справка — coach-help.

## Закрыто

Шаг Н17, 2026-11-02 — [plan-n17.md](../plan-n17.md).

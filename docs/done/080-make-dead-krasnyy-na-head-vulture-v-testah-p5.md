# 80. `make dead` красный на HEAD: vulture в тестах П5
status: done
priority: low
updated: 2026-11-13

На HEAD 8cbdd5b (2026-11-12, прогон партии 1 Н29) `make dead` падает: vulture —
`tests/test_agenda_calendar_edit.py:285, :292: unused attribute 'side_effect'` (60 %); файл шагом Н29 не тронут,
причина — не установлена. Рядом BACKLOG 58 (smells на HEAD сейчас 6).

## Закрыто
Шаг Г1, 2026-11-13, [docs/plan-g1.md](../plan-g1.md).

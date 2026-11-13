# 58. `make smells` красный на HEAD: 4 при пороге 0
status: done
priority: low
updated: 2026-11-13

На HEAD 6a69bcc (worktree, 2026-11-07) `make smells` даёт 4 при `SMELLS_MAX` 0 — в старых файлах
(`plan/service`, `sync/workload_sync` и др.), не от П1; `make check` встаёт на smells. Причина роста — не
установлена.

## Закрыто
Шаг Г1, 2026-11-13, [docs/plan-g1.md](../plan-g1.md).

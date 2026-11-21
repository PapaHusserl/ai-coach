Запись за прошлое («съел вчера ...»): к `food`/`weight` добавь `--at <YYYY-MM-DD>` (или `--at "YYYY-MM-DD HH:MM"`; только дата = 12:00; в будущее нельзя).

Поправить или удалить запись: найди id `uv run coach log food|weight [--date <YYYY-MM-DD>]`, покажи запись, и только после «да» правь или удаляй: `uv run coach edit|delete food|weight <id>` (аргументы - `cat .claude/agents/coach-help/food.md`, запускать как `uv run coach ...`; Claude Code спросит ещё раз). Правка текста еды сбрасывает КБЖУ - потом посчитай по coach-food.

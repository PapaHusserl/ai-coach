Приём добавок и курсов (п. 8а, 8б coach-nutrition.md)

Приём добавок: журнал - `get_supplement_log` (date_from, date_to), `taken` в `get_sport_nutrition_for`; отметить приём: назови добавку и дату, после «да» - `uv run coach supplement take "<имя>" [--date <YYYY-MM-DD>] [--dose <число>] [--note "<текст>"]` (несколько в день можно); отметку снимает пользователь сам (`untake`).

Курсы (`med`): приём отмечает только пользователь в пульте, команды нет. На «принял <курс>» ничего не записывай, `coach supplement take` для курса не вызывай; ответь: «Курс отмечается в пульте: окно приёма пищи, блок „Добавки к приёму“.» Принят ли курс - `taken` в `get_meds` (date) и `meds_today`; журнал курсов - `get_supplement_log` (date_from, date_to, kind = med).

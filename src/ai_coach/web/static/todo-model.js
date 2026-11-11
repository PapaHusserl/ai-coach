// Пульт: карточка «Туду» — чистые функции без DOM (тесты — tests/web/todo.test.mjs).

const DAY_MIN = 1440;
const SPAN_MIN = 30;
const NOON = 720;

// Куда можно перевести открытый пункт — как MOVES в workload/todo.py (тест сверяет по тексту).
const MOVES = {
	todo: [
		["doing", "в работу"],
		["done", "сделано"],
		["dropped", "отбросить"],
	],
	doing: [
		["todo", "в список"],
		["done", "сделано"],
		["dropped", "отбросить"],
	],
};

// Открытые пункты: doing первыми, затем по id; закрытые, если пришли, отбрасываются (Р3 = 2).
export function todoRows(view) {
	return view.items
		.filter((item) => item.state in MOVES)
		.sort((a, b) => (a.state === "doing" ? 0 : 1) - (b.state === "doing" ? 0 : 1) || a.id - b.id);
}

// Кнопки состояний пункта; у закрытых пусто.
export function moveButtons(state) {
	return (MOVES[state] ?? []).map(([next, label]) => ({ state: next, label }));
}

// Тело POST /api/todo.
export const todoPayload = (op, fields) => ({ op, ...fields });

// Время по умолчанию для переноса в календарь (Р5а): сегодня — ближайшие 5 минут, 30 минут, конец не позже
// 24:00; другой день — 12:00–12:30. now — Date по часам браузера, day — "YYYY-MM-DD".
export function todoSpan(now, day) {
	const pad = (value) => String(value).padStart(2, "0");
	const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
	if (day !== today) return { start: NOON, end: NOON + SPAN_MIN };
	const start = Math.min(Math.ceil((now.getHours() * 60 + now.getMinutes()) / 5) * 5, DAY_MIN - SPAN_MIN);
	return { start, end: start + SPAN_MIN };
}

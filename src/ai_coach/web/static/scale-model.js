// Пульт: шкала дня — чистые функции без DOM (тесты — tests/web/scale.test.mjs).

const DAY_MIN = 1440;
const EMPTY_FRAME = { start: 480, end: 1320 }; // пустой день: 08:00–22:00 (Р13)
const MARGIN = 60; // рамка бара ± 1 ч (Р1)
const NEW_MIN = 30; // новый пункт — всегда 30 минут (Р5)
const MIN_SPAN = 5;

// "2026-11-09T09:00:00" -> минуты от эпохи (по часам записи, без пояса)
const stamp = (iso) => Date.parse(`${iso.slice(0, 19)}Z`) / 60000;
const dayStamp = (day) => Date.parse(`${day}T00:00:00Z`) / 60000;
const isoAt = (minutes) => new Date(minutes * 60000).toISOString().slice(0, 19);

// Рамка шкалы: пункты и встречи (без all_day) ± 1 ч, в пределах суток; пустой день — 08:00–22:00.
export function frameOf(view) {
	const base = dayStamp(view.date);
	const rows = [...view.items, ...view.meetings].filter((row) => !row.all_day);
	if (rows.length === 0) return { ...EMPTY_FRAME };
	const start = Math.min(...rows.map((row) => stamp(row.start_at))) - base - MARGIN;
	const end = Math.max(...rows.map((row) => stamp(row.end_at))) - base + MARGIN;
	return { start: Math.max(start, 0), end: Math.min(end, DAY_MIN) };
}

// Минута рамки под x пикселей полосы шириной width; за краем — край рамки.
export function minuteAt(x, width, frame) {
	const inside = Math.min(Math.max(x, 0), width);
	return frame.start + ((frame.end - frame.start) * inside) / width;
}

export const snap = (min, step) => Math.round(min / step) * step;

// Положение блока в процентах рамки.
export function blockBox(row, frame) {
	const length = frame.end - frame.start;
	const begin = stamp(row.start_at);
	const from = begin - dayStamp(row.start_at.slice(0, 10)) - frame.start;
	return { left: (100 * from) / length, width: (100 * (stamp(row.end_at) - begin)) / length };
}

// Новые времена блока после сдвига на deltaMin минут: move — оба конца, resize — только конец (≥ 5 мин);
// всё внутри суток начала строки.
export function dragOutcome(mode, row, deltaMin) {
	const begin = stamp(row.start_at);
	const end = stamp(row.end_at);
	const dayStart = dayStamp(row.start_at.slice(0, 10));
	const dayEnd = dayStart + DAY_MIN; // границы суток строки: за них блок не уходит
	if (mode === "move") {
		const shift = Math.min(Math.max(deltaMin, dayStart - begin), Math.max(dayEnd - end, 0));
		return { start_at: isoAt(begin + shift), end_at: isoAt(end + shift) };
	}
	return { start_at: row.start_at, end_at: isoAt(Math.min(Math.max(end + deltaMin, begin + MIN_SPAN), Math.max(dayEnd, end))) };
}

// Новый пункт по клику: 30 минут от снапа, конец не позже 24:00; frame.end не ограничивает.
export function newSpan(min, frame) {
	void frame;
	const start = Math.min(snap(min, 5), DAY_MIN - NEW_MIN);
	return { start, end: start + NEW_MIN };
}

// Виды нового пункта (Р5 = 1): значение, подпись кнопки, слово по умолчанию в названии.
export const KINDS = [
	{ value: "task", label: "задача", word: "Задача" },
	{ value: "focus", label: "фокус", word: "Фокус" },
	{ value: "rest", label: "отдых", word: "Прогулка / отдых" },
	{ value: "meal", label: "еда", word: "Перекус" },
	{ value: "checkin", label: "чек-ин", word: "Чек-ин" },
];
// Опросники чек-ина (значения — SURVEYS в agenda/service.py), подписи кнопок.
export const SURVEYS = [
	{ value: "evening", label: "вечер" },
	{ value: "feel", label: "самочувствие" },
	{ value: "focus", label: "фокус" },
	{ value: "none", label: "напоминание" },
];
export const CATEGORIES = ["work", "personal", "hobby"]; // только у задачи, по умолчанию work

// Тело POST create: пустое название — слово вида; category только у задачи, survey только у чек-ина.
export function createPayload({ kind, category, survey, title, start_at, end_at }) {
	const word = KINDS.find((item) => item.value === kind).word;
	const body = { action: "create", kind, title: title.trim() || word, start_at, end_at };
	if (kind === "task") return { ...body, category };
	return kind === "checkin" ? { ...body, survey } : body;
}

// Повтор тренера не двигается (Н23 Р5 = 1); встреча — если сервер отдал editable (Р11 = 1).
export const locked = (row) => (row.source === "item" ? row.repeat != null : !row.editable);

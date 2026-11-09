// Пульт: модель плана дня — чистые функции без DOM (тесты — tests/web/pult.test.mjs, импорт через pult.js).

import { isFuture, isPast, markSummary, tabsFor } from "./marks-model.js";

const WEEKDAYS = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
export const MONTHS = [
	"января", "февраля", "марта", "апреля", "мая", "июня",
	"июля", "августа", "сентября", "октября", "ноября", "декабря",
];

// "2026-11-07T09:05:00" -> "09:05"
export function formatClock(iso) {
	return iso.slice(11, 16);
}

// "2026-11-07" -> "сб, 7 ноября"
export function formatDate(day) {
	const [year, month, date] = day.split("-").map(Number);
	const weekday = new Date(Date.UTC(year, month - 1, date)).getUTCDay();
	return `${WEEKDAYS[weekday]}, ${date} ${MONTHS[month - 1]}`;
}

// Ширина заполненной части бара, 0..100 %.
export function barPercent(elapsedMin, leftMin) {
	const total = elapsedMin + leftMin;
	if (total <= 0) return 0;
	return Math.min(100, Math.max(0, Math.round((elapsedMin / total) * 100)));
}

// "2026-11-07" + 1 -> "2026-11-08"
export function shiftDay(day, delta) {
	const [year, month, date] = day.split("-").map(Number);
	return new Date(Date.UTC(year, month - 1, date + delta)).toISOString().slice(0, 10);
}

// Идёт ли сейчас пункт: current — список {source, id} из /api/day.
export function isCurrent(current, source, id) {
	return current.some((c) => c.source === source && c.id === id);
}

// Строки дня: all_day сверху, остальные по началу; у каждой source, current, muted.
export function dayRows(view) {
	const rows = [
		...view.items.map((row) => ({ ...row, source: "item" })),
		...view.meetings.map((row) => ({ ...row, source: "meeting" })),
	];
	const marked = rows.map((row) => ({
		...row,
		current: isCurrent(view.current, row.source, row.id),
		muted: row.source === "meeting",
	}));
	const order = (a, b) => a.start_at.localeCompare(b.start_at);
	return [...marked.filter((r) => r.all_day).sort(order), ...marked.filter((r) => !r.all_day).sort(order)];
}

export const part = (min) => (min >= 60 ? `${Math.floor(min / 60)} ч ${min % 60} мин` : `${min} мин`);

// Подпись бара: "прошло 1 ч 30 мин / осталось 2 ч 0 мин".
export function barLabel(elapsedMin, leftMin) {
	return `прошло ${part(elapsedMin)} / осталось ${part(leftMin)}`;
}

const KIND_LABELS = {
	task: "задача",
	focus: "фокус",
	practice: "практика",
	rest: "отдых",
	meal: "еда",
	training: "тренировка",
	checkin: "чек-ин",
};

// Минуты от a до b, ISO-строки одного формата ("2026-11-07T09:05:00").
function minutesBetween(a, b) {
	return Math.round((Date.parse(b) - Date.parse(a)) / 60000);
}

// У пункта есть окно отметок (встречи и пункты без окна — нет).
export function hasWindow(row) {
	// У «Готовки» (kind meal без ключа meal) окна нет, Р7.
	return row.source === "item" && tabsFor(row.kind).length > 0 && (row.kind !== "meal" || row.meal != null);
}

// Какой пункт раскрыт: choice — id, выбранный кликом; false — свёрнуто всё; null — раскрыт идущий.
export function openedId(choice, rows) {
	if (choice === false) return null;
	const windowed = rows.filter(hasWindow);
	const chosen = windowed.find((row) => row.id === choice);
	return (chosen ?? windowed.find((row) => row.current))?.id ?? null;
}

// Статус прошедшего пункта с окном: красный «не заполнено», зелёная сводка или null.
function pastStatus(row) {
	if (row.due) return { text: "не заполнено", tone: "bad" };
	const summary = markSummary(row.marks, row.training?.fact);
	return summary ? { text: summary, tone: "good" } : null;
}

// Ближайший будущий пункт с окном — только на сегодняшнем дне (на чужом «через N» нет); без него undefined.
export function nextRow(rows, view) {
	if (view.date !== view.now.slice(0, 10)) return undefined;
	return rows.find((row) => hasWindow(row) && !row.all_day && isFuture(row, view.now));
}

// Статус справа в строке (Р4): {text, tone}; tone — live | good | bad | "". isNext — ближайший ли это пункт.
export function rowStatus(row, now, isNext) {
	if (row.current) return { text: "идёт", tone: "live" };
	if (!hasWindow(row)) return { text: "", tone: "" };
	const known = isPast(row, now)
		? pastStatus(row)
		: isNext && { text: `через ${part(minutesBetween(now, row.start_at))}`, tone: "" };
	return known || { text: KIND_LABELS[row.kind] ?? "", tone: "" };
}

// Бар текущего пункта: {percent, elapsedMin, leftMin, until}; у пункта на весь день бара нет (null).
export function itemProgress(row, now) {
	if (row.all_day) return null;
	const total = minutesBetween(row.start_at, row.end_at);
	const elapsedMin = Math.min(Math.max(minutesBetween(row.start_at, now), 0), total);
	const percent = Math.round((elapsedMin / total) * 100);
	return { percent, elapsedMin, leftMin: total - elapsedMin, until: formatClock(row.end_at) };
}

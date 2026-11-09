// Пульт: модель вкладки «Тренировки» — чистые функции без DOM (тесты — tests/web/pult.test.mjs, импорт через pult.js).

import { MONTHS } from "./pult-model.js";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const FACT_PILLS = {
	done: { text: "сделано", tone: "good" },
	different: { text: "выполнено иначе", tone: "warn" },
	skipped: { text: "пропущено", tone: "muted" },
};
const EXTRA_PILL = { text: "вне плана", tone: "muted" };
const REST_PILL = { text: "отдых", tone: "muted" };

function planPill(workout) {
	return { text: workout.status === "pushed" ? "на часах" : "в плане", tone: "muted" };
}

// Строки дня {title, pill}: каждый план (отменённые не в счёт) с плашкой своего факта (по planned_id:
// сделано, иначе, пропущено), без факта — плашка плана; затем активности вне плана; пусто — «—» и «отдых».
function dayItems(entry) {
	const items = entry.planned
		.filter((w) => w.status !== "cancelled")
		.map((w) => {
			const own = entry.fact.find((f) => f.planned_id === w.id);
			return { title: w.name, pill: own ? FACT_PILLS[own.kind] : planPill(w) };
		});
	const extras = entry.fact.filter((f) => f.kind === "extra").map((f) => ({ title: f.name, pill: EXTRA_PILL }));
	const all = [...items, ...extras];
	return all.length ? all : [{ title: "—", pill: REST_PILL }];
}

// Семь строк недели из ответа /api/week: {date, label «Пн 9», today, items: [{title, pill: {text, tone}}]};
// today — календарное сегодня (рамка), выбранный день на неделе не отмечен.
export function weekRows(week, today) {
	return week.days.map((entry, index) => ({
		date: entry.date,
		label: `${WEEKDAYS[index]} ${Number(entry.date.slice(8))}`,
		today: entry.date === today,
		items: dayItems(entry),
	}));
}

// «Неделя 9–15 ноября»; через границу месяца — «Неделя 26 октября – 1 ноября».
export function weekTitle(week) {
	const [first, last] = [week.days[0].date, week.days.at(-1).date];
	const [dayA, dayB] = [Number(first.slice(8)), Number(last.slice(8))];
	const [monthA, monthB] = [MONTHS[Number(first.slice(5, 7)) - 1], MONTHS[Number(last.slice(5, 7)) - 1]];
	if (monthA === monthB) return `Неделя ${dayA}–${dayB} ${monthA}`;
	return `Неделя ${dayA} ${monthA} – ${dayB} ${monthB}`;
}

// Точки графика [x, y] для ряда values в рамке box {x0, x1, y0, y1, min, max}: x равными шагами от x0 до x1,
// y0 — верх рамки (max), y1 — низ (min).
export function chartPoints(values, box) {
	const steps = Math.max(values.length - 1, 1);
	return values.map((value, index) => [
		box.x0 + (index * (box.x1 - box.x0)) / steps,
		box.y1 - ((value - box.min) / (box.max - box.min)) * (box.y1 - box.y0),
	]);
}

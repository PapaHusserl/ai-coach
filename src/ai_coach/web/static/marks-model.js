// Пульт: модель окна отметок — чистые функции и таблицы, без DOM (тесты — tests/web/marks.test.mjs).
// Полюса шкал — слова из coach-help/wellbeing.md (тест в tests/test_skills_help.py держит расхождение).

const TABS = {
	"task": ["rating", "feel", "slip"],
	"focus": ["rating", "feel", "slip"],
	"practice": ["done", "feel", "slip"],
	"rest": ["done", "feel", "slip"],
	"checkin": ["checkin"],
};
export const TAB_LABELS = {
	rating: "Оценка",
	feel: "Самочувствие",
	slip: "Срыв",
	done: "Сделал",
	checkin: "Чек-ин",
};
export const FIELDS = {
	focus: { label: "Фокус", low: "рассеян", high: "полностью собран" },
	fatigue: { label: "Усталость", low: "свеж", high: "выжат" },
	effort: { label: "Усилие", low: "легко взялся", high: "через силу" },
	score: { label: "Самочувствие", low: "плохо", high: "отлично" },
	mood: { label: "Настроение", low: "плохое", high: "отличное" },
	stress: { label: "Стресс", low: "нет", high: "сильный" },
	thoughts: { label: "Мысли о работе вечером", low: "не думал", high: "всё время" },
	hindrance: { label: "Помехи", low: "почти не было", high: "весь день" },
	valuable: { label: "Ценность сделанного", low: "почти ничего", high: "всё ценное" },
};
export const TAB_FIELDS = {
	rating: ["focus", "fatigue", "effort"],
	feel: ["score"],
	checkin: ["score", "mood", "stress", "thoughts", "hindrance", "valuable"],
};
// Обязательные шкалы вкладки; остальные из TAB_FIELDS — по желанию (повторный клик снимает).
export const REQUIRED = {
	rating: ["focus", "fatigue", "effort"],
	feel: ["score"],
	checkin: ["score"],
};
export const HOURS = { work: "Работа, ч", hobby: "Хобби, ч", rest: "Отдых, ч" };
export const FLOW_CHOICES = [
	{ label: "Да", flow: 1 },
	{ label: "Нет", flow: 0 },
];
export const DONE_CHOICES = [
	{ label: "Сделал", done: 1 },
	{ label: "Пропустил", done: 0 },
	{ label: "Снять отметку", done: null },
];
// Ошибки про пункт сервер пишет текстом; остальные — протокольные (Р10).
const ITEM_ERRORS = [
	"Пункт ещё не начался",
	"Пункта в этот день нет",
	"У этого пункта пока нет окна",
	"Текст не может быть пустым",
	"Часы (",
];

// Вкладки окна пункта по его типу; пусто — окна нет.
export function tabsFor(kind) {
	return TABS[kind] ?? [];
}

// Прошёл ли пункт: конец не позже now (ISO-строки одного формата).
export function isPast(row, now) {
	return row.end_at <= now;
}

export function isFuture(row, now) {
	return row.start_at > now;
}

// Краткая отметка в строке пункта: последняя оценка и «сделал / пропустил».
export function markSummary(marks) {
	const parts = [];
	const last = marks.ratings.at(-1);
	if (last) parts.push(`${last.focus}/${last.fatigue}/${last.effort}`);
	if (marks.done) parts.push(marks.done.done === 1 ? "сделал" : "пропустил");
	return parts.join(" · ");
}

// «Самочувствие 4, настроение 3, стресс 2»: у записи чек-ина есть настроение и стресс, пустые не выводятся.
function feelHead(r) {
	const parts = [`Самочувствие ${r.score}`];
	if (r.mood != null) parts.push(`настроение ${r.mood}`);
	if (r.stress != null) parts.push(`стресс ${r.stress}`);
	return parts.join(", ");
}

// Все отметки пункта по времени: {time: "HH:MM", tab, text}.
export function historyRows(marks) {
	const withText = (head, text) => (text ? `${head} — ${text}` : head);
	const rows = [
		...marks.ratings.map((r) => ({
			at: r.logged_at,
			tab: "rating",
			text: withText(`Оценка ${r.focus}/${r.fatigue}/${r.effort}`, r.text),
		})),
		...marks.feel.map((r) => ({
			at: r.logged_at,
			tab: "feel",
			text: withText(feelHead(r), r.text),
		})),
		...marks.slips.map((r) => ({ at: r.logged_at, tab: "slip", text: withText("Срыв", r.text) })),
	];
	if (marks.done) {
		const word = marks.done.done === 1 ? "Сделал" : "Пропустил";
		rows.push({ at: marks.done.logged_at, tab: "done", text: word });
	}
	rows.sort((a, b) => a.at.localeCompare(b.at));
	return rows.map((r) => ({ time: r.at.slice(11, 16), tab: r.tab, text: r.text }));
}

// Можно ли сохранять вкладку: у шкал выбраны все значения.
export function canSave(tab, form) {
	return (REQUIRED[tab] ?? []).every((name) => Number.isInteger(form[name]));
}

// Часы из поля ввода: "6,5" -> 6.5; пусто или не число -> null.
function hoursValue(raw) {
	const text = String(raw ?? "").trim().replace(",", ".");
	const value = text === "" ? Number.NaN : Number(text);
	return Number.isFinite(value) ? value : null;
}

// Тело POST /api/mark: числа — числами, пустые поля не уходят.
export function buildPayload(tab, form) {
	const payload = { event_id: form.event_id, date: form.date, mark: tab };
	for (const name of TAB_FIELDS[tab] ?? []) {
		if (REQUIRED[tab].includes(name) || Number.isInteger(form[name])) payload[name] = Number(form[name]);
	}
	if (tab === "checkin") {
		for (const name of Object.keys(HOURS)) {
			const hours = hoursValue(form[name]);
			if (hours !== null) payload[name] = hours;
		}
		if (form.flow === 0 || form.flow === 1) payload.flow = form.flow;
	}
	if (tab === "done") payload.done = form.done === null ? null : Number(form.done);
	const text = (form.text ?? "").trim();
	if (text) payload.text = text;
	return payload;
}

// Что показать при ошибке: про пункт — текст сервера, остальное — «ошибка пульта (код N)».
export function errorText(status, text) {
	if (status === 400 && ITEM_ERRORS.some((start) => text.startsWith(start))) return text;
	return `Не сохранилось, ошибка пульта (код ${status}).`;
}

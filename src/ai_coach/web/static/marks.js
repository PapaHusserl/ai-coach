// Пульт: окно отметок пункта. Чистые функции — для тестов (tests/web), DOM — в функциях, зовутся только в браузере.
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
};
const TAB_FIELDS = { rating: ["focus", "fatigue", "effort"], feel: ["score"] };
const DONE_CHOICES = [
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
			text: withText(`Самочувствие ${r.score}`, r.text),
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
	return (TAB_FIELDS[tab] ?? []).every((name) => Number.isInteger(form[name]));
}

// Тело POST /api/mark: числа — числами, пустой текст не уходит.
export function buildPayload(tab, form) {
	const payload = { event_id: form.event_id, date: form.date, mark: tab };
	for (const name of TAB_FIELDS[tab] ?? []) payload[name] = Number(form[name]);
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

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

const state = { id: null, day: null, tab: null, future: false, forms: {}, reload: null };
// Красная строка ошибки стоит в форме над «Сохранить» и переезжает вместе с ней.
const errorLine = typeof document === "undefined" ? null : el("p", "error");

export function setupMarks(reload) {
	state.reload = reload;
	const dialog = document.getElementById("marks");
	dialog.addEventListener("close", () => {
		state.id = null;
	});
}

function showError(text) {
	errorLine.textContent = text;
	errorLine.hidden = text === "";
}

async function send(tab, text) {
	showError("");
	const form = { ...state.forms[tab], event_id: state.id, date: state.day, text };
	const body = JSON.stringify(buildPayload(tab, form));
	let status = 0;
	let reply = "";
	try {
		const response = await fetch("/api/mark", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body,
		});
		status = response.status;
		reply = await response.text();
		if (response.ok) {
			state.forms[tab] = {};
			await state.reload();
			buildForm();
			return;
		}
	} catch (error) {
		console.error("POST /api/mark не удался", error);
	}
	console.error("POST /api/mark", status, reply);
	showError(errorText(status, reply));
}

function scale(tab, name, save) {
	const field = FIELDS[name];
	const form = state.forms[tab];
	const wrap = el("div", "field");
	wrap.append(el("div", "label", field.label));
	const line = el("div", "scale");
	line.append(el("span", "pole", field.low));
	const buttons = [];
	for (let value = 1; value <= 5; value += 1) {
		const button = el("button", "", String(value));
		button.type = "button";
		button.setAttribute("aria-pressed", String(form[name] === value));
		button.addEventListener("click", () => {
			form[name] = value;
			for (const other of buttons) other.setAttribute("aria-pressed", String(other === button));
			save.disabled = !canSave(tab, form);
		});
		buttons.push(button);
		line.append(button);
	}
	line.append(el("span", "pole", field.high));
	wrap.append(line);
	return wrap;
}

function buildForm() {
	const box = document.getElementById("marks-form");
	box.replaceChildren();
	const tab = state.tab;
	state.forms[tab] ??= {};
	if (state.future) {
		box.append(el("p", "hint", "Ещё не началось."));
		return;
	}
	if (tab === "checkin") {
		box.append(el("p", "hint", "Анкета чек-ина пока не готова."));
		return;
	}
	if (tab === "done") {
		const line = el("div", "choices");
		for (const choice of DONE_CHOICES) {
			const button = el("button", "", choice.label);
			button.type = "button";
			button.addEventListener("click", () => {
				state.forms.done = { done: choice.done };
				send("done", "");
			});
			line.append(button);
		}
		box.append(errorLine, line);
		return;
	}
	const save = el("button", "save", "Сохранить");
	save.type = "button";
	const text = el("textarea", "text");
	text.rows = 2;
	for (const name of TAB_FIELDS[tab] ?? []) box.append(scale(tab, name, save));
	box.append(text, errorLine, save);
	save.disabled = !canSave(tab, state.forms[tab]);
	save.addEventListener("click", () => send(tab, text.value));
}

function buildTabs(kind) {
	const tabs = document.getElementById("marks-tabs");
	tabs.replaceChildren();
	for (const tab of tabsFor(kind)) {
		const button = el("button", "tab", TAB_LABELS[tab]);
		button.type = "button";
		button.setAttribute("aria-pressed", String(tab === state.tab));
		button.addEventListener("click", () => {
			state.tab = tab;
			showError("");
			buildTabs(kind);
			buildForm();
		});
		tabs.append(button);
	}
}

function buildHistory(row) {
	document.getElementById("marks-sub").textContent = markSummary(row.marks) || (row.due ? "не отмечено" : "");
	const list = document.getElementById("marks-history");
	list.replaceChildren();
	for (const entry of historyRows(row.marks)) list.append(el("li", "", `${entry.time} · ${entry.text}`));
}

// Открыть окно пункта row дня day; view — ответ /api/day.
export function openMarks(row, day, view) {
	state.id = row.id;
	state.day = day;
	state.tab = tabsFor(row.kind)[0];
	state.future = isFuture(row, view.now);
	state.forms = {};
	const clock = `${row.start_at.slice(11, 16)}–${row.end_at.slice(11, 16)}`;
	document.getElementById("marks-title").textContent = `${clock} ${row.title}`;
	showError("");
	buildTabs(row.kind);
	buildForm();
	buildHistory(row);
	document.getElementById("marks").showModal();
}

// После load(): перерисовать историю и подпись открытого окна; форма ввода не трогается.
export function refreshMarks(view) {
	const dialog = document.getElementById("marks");
	if (state.id === null || !dialog.open) return;
	const row = view.items.find((item) => item.id === state.id);
	if (!row) return;
	buildHistory(row);
	const future = isFuture(row, view.now);
	if (future !== state.future) {
		state.future = future;
		buildForm();
	}
}

// Пульт: окно отметок пункта, только DOM (зовётся в браузере). Таблицы и чистые функции — marks-model.js,
// их тесты — tests/web/marks.test.mjs; здесь они же реэкспортируются.
import {
	DONE_CHOICES,
	FIELDS,
	FLOW_CHOICES,
	HOURS,
	REQUIRED,
	TAB_FIELDS,
	TAB_LABELS,
	buildPayload,
	canSave,
	errorText,
	historyRows,
	isFuture,
	markSummary,
	tabsFor,
} from "./marks-model.js";

export * from "./marks-model.js";

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
	const optional = !REQUIRED[tab].includes(name);
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
			form[name] = optional && form[name] === value ? null : value;
			for (const other of buttons) {
				other.setAttribute("aria-pressed", String(buttons.indexOf(other) + 1 === form[name]));
			}
			save.disabled = !canSave(tab, form);
		});
		buttons.push(button);
		line.append(button);
	}
	line.append(el("span", "pole", field.high));
	wrap.append(line);
	return wrap;
}

// Часы дня чек-ина: поля ввода, значение живёт в форме вкладки.
function hoursFields(form) {
	const line = el("div", "hours");
	for (const [name, label] of Object.entries(HOURS)) {
		const wrap = el("label", "hour", label);
		const input = el("input");
		input.type = "number";
		input.min = "0";
		input.max = "24";
		input.step = "0.5";
		input.inputMode = "decimal";
		input.value = form[name] ?? "";
		input.addEventListener("input", () => {
			form[name] = input.value;
		});
		wrap.append(input);
		line.append(wrap);
	}
	return line;
}

// Погружение: да / нет, повторный клик снимает выбор.
function flowField(form) {
	const wrap = el("div", "field");
	wrap.append(el("div", "label", "Погружение"));
	const line = el("div", "choices");
	const buttons = [];
	for (const choice of FLOW_CHOICES) {
		const button = el("button", "", choice.label);
		button.type = "button";
		button.setAttribute("aria-pressed", String(form.flow === choice.flow));
		button.addEventListener("click", () => {
			form.flow = form.flow === choice.flow ? null : choice.flow;
			for (const [index, other] of buttons.entries()) {
				other.setAttribute("aria-pressed", String(FLOW_CHOICES[index].flow === form.flow));
			}
		});
		buttons.push(button);
		line.append(button);
	}
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
	if (tab === "checkin") box.append(hoursFields(state.forms[tab]), flowField(state.forms[tab]));
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

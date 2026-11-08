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
	foodSummary,
	historyRows,
	isFuture,
	markSummary,
	remainingText,
	tabsFor,
} from "./marks-model.js";

export * from "./marks-model.js";

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

const state = { id: null, day: null, tab: null, future: false, forms: {}, reload: null, meal: null, busy: false };
// Красная строка ошибки стоит в форме над «Сохранить» и переезжает вместе с ней.
const errorLine = typeof document === "undefined" ? null : el("p", "error");
// Узел окна один на страницу: переезжает под раскрытую строку и переживает перерисовку списка (Р1 = 2).
const ui = {};
let toastTimer;
// Черновики формы по «день:id пункта» до перезагрузки страницы (Р17 = 1); у каждого — формы по вкладкам, текст в form.text.
const drafts = {};

function paneNode() {
	if (!ui.pane) {
		ui.pane = el("div", "pane");
		ui.sub = el("p", "bar-label");
		ui.tabs = el("div", "tabs");
		ui.tabs.setAttribute("role", "tablist");
		ui.form = el("div", "blk");
		ui.history = el("ul", "history");
		ui.pane.append(ui.sub, ui.tabs, ui.form, ui.history);
	}
	return ui.pane;
}

// Всплывающее «Записано» (Р9).
function toast(text) {
	if (!ui.toast) {
		ui.toast = el("div", "toast");
		ui.toast.setAttribute("role", "status");
		document.body.append(ui.toast);
	}
	ui.toast.textContent = text;
	ui.toast.classList.add("show");
	clearTimeout(toastTimer);
	toastTimer = setTimeout(() => ui.toast.classList.remove("show"), 1800);
}

export function setupMarks(reload) {
	state.reload = reload;
}

function showError(text) {
	errorLine.textContent = text;
	errorLine.hidden = text === "";
}

// Пока запись уходит и список перезагружается, второй клик не создаёт вторую запись.
async function send(tab, text) {
	if (state.busy) return;
	state.busy = true;
	try {
		await sendNow(tab, text);
	} finally {
		state.busy = false;
	}
}

async function sendNow(tab, text) {
	showError("");
	const forms = state.forms;
	const form = { ...forms[tab], event_id: state.id, date: state.day, text };
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
			forms[tab] = {};
			await state.reload();
			buildForm();
			toast("Записано");
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
	// Строка: название, кнопки 1–5, полюса словами (Р8); у обязательной пустой шкалы название красное.
	const wrap = el("div", "sr");
	const line = el("div", "qs");
	const buttons = [];
	const mark = () => {
		wrap.classList.toggle("empty", !optional && !Number.isInteger(form[name]));
		for (const [index, other] of buttons.entries()) {
			other.setAttribute("aria-pressed", String(index + 1 === form[name]));
		}
	};
	for (let value = 1; value <= 5; value += 1) {
		const button = el("button", "", String(value));
		button.type = "button";
		button.addEventListener("click", () => {
			form[name] = optional && form[name] === value ? null : value;
			mark();
			save.disabled = !canSave(tab, form);
		});
		buttons.push(button);
		line.append(button);
	}
	wrap.append(el("span", "", field.label), line, el("span", "h", `${field.low} — ${field.high}`));
	mark();
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
	const wrap = el("div", "sr");
	const line = el("div", "yn");
	const buttons = [];
	for (const choice of FLOW_CHOICES) {
		const button = el("button", choice.flow === 1 ? "y" : "n", choice.label);
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
	wrap.append(el("span", "", "Погружение"), line);
	return wrap;
}

// Остаток дня и «Записано ✓» у еды: меняется только текст узлов, форма ввода не пересобирается.
function fillMeal() {
	const eaten = foodSummary(state.meal);
	ui.saved.textContent = `Записано ✓ ${eaten}`;
	ui.saved.hidden = eaten === "";
	ui.left.textContent = remainingText(state.meal);
}

function buildForm() {
	const box = ui.form;
	box.replaceChildren();
	ui.saved = null;
	ui.left = null;
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
	const food = tab === "food";
	const save = el("button", "save", food ? "Записать" : "Сохранить");
	save.type = "button";
	const text = el("textarea", "text");
	text.rows = 2;
	text.value = state.forms[tab].text ?? "";
	text.addEventListener("input", () => {
		state.forms[tab].text = text.value;
		if (food) save.disabled = !canSave(tab, state.forms[tab]);
	});
	if (food) {
		ui.saved = el("p", "saved");
		ui.left = el("p", "bar-label");
		fillMeal();
		box.append(ui.saved, ui.left);
		text.placeholder = "напиши, что съел";
	}
	for (const name of TAB_FIELDS[tab] ?? []) box.append(scale(tab, name, save));
	if (tab === "checkin") box.append(hoursFields(state.forms[tab]), flowField(state.forms[tab]));
	box.append(text, errorLine, save);
	save.disabled = !canSave(tab, state.forms[tab]);
	save.addEventListener("click", () => send(tab, text.value));
}

function buildTabs(kind) {
	const tabs = ui.tabs;
	tabs.replaceChildren();
	for (const tab of tabsFor(kind)) {
		const button = el("button", "tab", TAB_LABELS[tab]);
		button.type = "button";
		button.setAttribute("role", "tab");
		button.setAttribute("aria-selected", String(tab === state.tab));
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
	ui.sub.textContent = row.due ? "не отмечено" : markSummary(row.marks);
	ui.sub.classList.toggle("bad", Boolean(row.due));
	ui.history.replaceChildren();
	for (const entry of historyRows(row.marks)) ui.history.append(el("li", "", `${entry.time} · ${entry.text}`));
}

function startPane(row, view) {
	state.id = row.id;
	state.day = view.date;
	state.tab = tabsFor(row.kind)[0];
	state.future = isFuture(row, view.now);
	state.forms = drafts[`${view.date}:${row.id}`] ??= {};
	showError("");
	buildTabs(row.kind);
	buildForm();
}

// Раскрыть окно пункта row под строкой item; view — ответ /api/day. Тот же пункт того же дня после load():
// узел переезжает в новую строку, обновляются история и подпись, форма ввода не трогается.
export function mountMarks(item, row, view) {
	const pane = paneNode();
	state.meal = row.meal ?? null;
	if (state.id !== row.id || state.day !== view.date) startPane(row, view);
	const future = isFuture(row, view.now);
	if (future !== state.future) {
		state.future = future;
		buildForm();
	}
	if (ui.left) fillMeal();
	buildHistory(row);
	item.append(pane);
}

// Свернуть окно: узел уходит из списка, черновик остаётся (Р17).
export function unmountMarks() {
	ui.pane?.remove();
	state.id = null;
}

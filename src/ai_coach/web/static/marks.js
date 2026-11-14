// Пульт: окно отметок пункта, только DOM (зовётся в браузере). Таблицы и чистые функции — marks-model.js,
// их тесты — tests/web/marks.test.mjs; здесь они же реэкспортируются.
import {
	DONE_CHOICES,
	TAB_FIELDS,
	buildPayload,
	canSave,
	errorText,
	foodSummary,
	historyRows,
	isFuture,
	isPast,
	markSummary,
	remainingText,
	tabLabel,
	tabsFor,
	who5DayLine,
	who5Line,
} from "./marks-model.js";
import { el } from "./dom.js";
import { flowField, hoursFields, scale } from "./marks-fields.js";
import { offersBlock } from "./offers-pane.js";
import { toast } from "./toast.js";
import { fillTraining } from "./training-pane.js";
import { who5Fields } from "./who5-fields.js";

export * from "./marks-model.js";

const state = { id: null, day: null, tab: null, future: false, past: false, forms: {}, reload: null, meal: null, offer: 0, training: null, who5: null, busy: false };
// Красная строка ошибки стоит в форме над «Сохранить» и переезжает вместе с ней.
const errorLine = typeof document === "undefined" ? null : el("p", "error");
// Узел окна один на страницу: переезжает под раскрытую строку и переживает перерисовку списка (Р1 = 2).
const ui = {};
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

export function setupMarks(reload) {
	state.reload = reload;
}

function showError(text) {
	errorLine.textContent = text;
	errorLine.hidden = text === "";
}

// Пока запись уходит и список перезагружается, второй клик не создаёт вторую запись.
async function send(tab, text, extra = {}) {
	if (state.busy) return;
	state.busy = true;
	try {
		await sendNow(tab, text, extra);
	} finally {
		state.busy = false;
	}
}

async function sendNow(tab, text, extra) {
	showError("");
	const forms = state.forms;
	const form = { ...forms[tab], ...extra, event_id: state.id, date: state.day, text };
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

// Остаток дня и «Записано ✓» у еды: меняется только текст узлов, форма ввода не пересобирается.
function fillMeal() {
	const eaten = foodSummary(state.meal);
	ui.saved.textContent = `Записано ✓ ${eaten}`;
	ui.saved.hidden = eaten === "";
	ui.left.textContent = remainingText(state.meal);
	fillOffers();
}

// Варианты блюд и подвал «Итого»: живут по минутам вместе с остатком, textarea не трогается.
function fillOffers() {
	const count = state.meal.offers.length;
	state.offer = Math.min(state.offer, Math.max(count - 1, 0));
	const take = state.future ? null : takeOffer; // у будущего пункта «Съел» нет (Р36)
	ui.offers.replaceChildren(...(count ? offersBlock(state.meal, state.offer, pickOffer, take) : []));
	if (!ui.save) return;
	ui.save.textContent = saveLabel(true, state.meal.offers);
	ui.text.placeholder = count ? "или напиши, что съел на самом деле" : "напиши, что съел";
}

// Узел окна тренировки (шаги или факт); минутный load перерисовывает его в mountMarks.
function trainingNode() {
	ui.train = el("div", "fact");
	fillTraining(ui.train, state.training, state.past);
	return ui.train;
}

function pickOffer(index) {
	state.offer = index;
	fillOffers();
}

function takeOffer(offer) {
	send("food", "", { offer_id: offer.id });
}

// Кнопки «Сделал» / «Пропустил»: клик сразу отправляет.
function doneChoices() {
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
	return line;
}

function saveLabel(food, offers) {
	if (!food) return "Сохранить";
	return offers.length ? "Записать своё" : "Записать";
}

// Верх окна еды: «Записано ✓», остаток дня, варианты блюд.
function mealHead(box) {
	ui.saved = el("p", "saved");
	ui.left = el("p", "bar-label");
	ui.offers = el("div");
	fillMeal();
	box.append(ui.saved, ui.left, ui.offers);
}

function buildForm() {
	const box = ui.form;
	box.replaceChildren();
	ui.saved = null;
	ui.left = null;
	ui.offers = null;
	ui.save = null;
	ui.text = null;
	ui.train = null;
	const tab = state.tab;
	state.forms[tab] ??= {};
	if (state.future) {
		box.append(el("p", "hint", "Ещё не началось."));
		if (tab === "food") mealHead(box); // остаток и варианты без «Съел» и без поля «своё» (Р36)
		if (tab === "done" && state.training) box.append(trainingNode()); // шаги плана без кнопок (Р24)
		return;
	}
	if (tab === "done") {
		if (state.training) box.append(trainingNode());
		box.append(errorLine, doneChoices());
		return;
	}
	if (tab === "who5" && state.who5) {
		box.append(el("p", "saved", who5DayLine(state.who5))); // замер за день один (Р11)
		return;
	}
	const food = tab === "food";
	const save = el("button", "save", saveLabel(food, []));
	save.type = "button";
	const text = el("textarea", "text");
	text.rows = 2;
	text.value = state.forms[tab].text ?? "";
	text.addEventListener("input", () => {
		state.forms[tab].text = text.value;
		if (food) save.disabled = !canSave(tab, state.forms[tab]);
	});
	if (food) {
		ui.save = save;
		ui.text = text;
		mealHead(box);
	}
	for (const name of TAB_FIELDS[tab] ?? []) box.append(scale(tab, state.forms[tab], name, save));
	if (tab === "who5") box.append(who5Fields(state.forms[tab], save));
	if (tab === "checkin") {
		box.append(hoursFields(state.forms[tab], state.day), flowField(state.forms[tab]));
	}
	box.append(text, errorLine, save);
	save.disabled = !canSave(tab, state.forms[tab]);
	save.addEventListener("click", () => send(tab, text.value));
}

function buildTabs(kind, survey) {
	const tabs = ui.tabs;
	tabs.replaceChildren();
	for (const tab of tabsFor(kind, survey)) {
		const button = el("button", "tab", tabLabel(kind, tab));
		button.type = "button";
		button.setAttribute("role", "tab");
		button.setAttribute("aria-selected", String(tab === state.tab));
		button.addEventListener("click", () => {
			state.tab = tab;
			showError("");
			buildTabs(kind, survey);
			buildForm();
		});
		tabs.append(button);
	}
}

function buildHistory(row) {
	const summary = [markSummary(row.marks, row.training?.fact), row.who5 ? who5Line(row.who5) : ""];
	ui.sub.textContent = row.due ? "не отмечено" : summary.filter(Boolean).join(" · ");
	ui.sub.classList.toggle("bad", Boolean(row.due));
	ui.history.replaceChildren();
	for (const entry of historyRows(row.marks)) ui.history.append(el("li", "", `${entry.time} · ${entry.text}`));
	if (row.who5) ui.history.append(el("li", "", `${row.who5.logged_at.slice(11, 16)} · ${who5Line(row.who5)}`));
}

function startPane(row, view) {
	state.id = row.id;
	state.day = view.date;
	state.tab = tabsFor(row.kind, row.survey)[0];
	state.future = isFuture(row, view.now);
	state.forms = drafts[`${view.date}:${row.id}`] ??= {};
	state.offer = 0;
	showError("");
	buildTabs(row.kind, row.survey);
	buildForm();
}

// Раскрыть окно пункта row под строкой item; view — ответ /api/day. Тот же пункт того же дня после load():
// узел переезжает в новую строку, обновляются история и подпись, форма ввода не трогается.
export function mountMarks(item, row, view) {
	const pane = paneNode();
	state.meal = row.meal ?? null;
	state.training = row.training ?? null;
	state.who5 = row.who5 ?? null;
	state.past = isPast(row, view.now);
	if (state.id !== row.id || state.day !== view.date) startPane(row, view);
	const future = isFuture(row, view.now);
	if (future !== state.future) {
		state.future = future;
		buildForm();
	}
	if (ui.left) fillMeal();
	if (ui.train && state.training) fillTraining(ui.train, state.training, state.past); // факт мог прийти после coach sync
	buildHistory(row);
	item.append(pane);
}

// Свернуть окно: узел уходит из списка, черновик остаётся (Р17).
export function unmountMarks() {
	ui.pane?.remove();
	state.id = null;
}

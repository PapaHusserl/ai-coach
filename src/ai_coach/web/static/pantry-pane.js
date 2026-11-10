// Пульт: вкладка «Еда» — кладовая и КБЖУ дня, только DOM (зовётся в браузере). Чистые функции — pantry-model.js.

import { el } from "./dom.js";
import { remainingText } from "./marks-model.js";
import { pantryRows, parseDelta } from "./pantry-model.js";
import { postJson } from "./post.js";
import { toast } from "./toast.js";

const UNITS = ["g", "ml", "pcs"];

let current = null; // { day, today } — для повтора после записи
let busy = false;
let unit = "g";

function node(id) {
	return document.getElementById(id);
}

function showNote(text) {
	const note = node("pantry-note");
	note.textContent = text;
	note.hidden = !text;
}

// Занято: идёт запись или фокус в поле вкладки — таймер её не перерисовывает.
export function pantryBusy() {
	const panel = document.querySelector('[data-panel="food"]');
	const active = document.activeElement;
	return busy || (!panel.hidden && panel.contains(active) && active.tagName === "INPUT");
}

// Р20 = 1: успех без предупреждения — «Записано»; предупреждение — под таблицей до следующей записи.
async function write(payload) {
	busy = true;
	showNote("");
	const result = await postJson("/api/pantry", payload);
	busy = false;
	if (!result.ok) {
		showNote(result.text);
		return false;
	}
	const { warning } = JSON.parse(result.body);
	if (warning) showNote(warning);
	else toast("Записано");
	await loadPantry(current.day, current.today);
	return true;
}

function rowNode(row) {
	const tr = el("tr", row.state);
	const input = el("input");
	input.size = 5;
	input.placeholder = "+200";
	input.setAttribute("aria-label", `Изменить остаток: ${row.item}`);
	const apply = () => {
		const delta = parseDelta(input.value);
		if (!delta) return showNote("Нужно число: +200, -50 или 120.");
		write({ ...delta, item: row.item, unit: row.unit });
	};
	input.addEventListener("keydown", (event) => {
		if (event.key === "Enter") apply();
	});
	const step = (op) => () => write({ op, item: row.item, qty: row.step, unit: row.unit });
	const less = el("button", "", "−");
	const more = el("button", "", "+");
	less.addEventListener("click", step("use"));
	more.addEventListener("click", step("add"));
	const left = el("td", "qty");
	left.append(less, ` ${row.qty} ${row.unit} `, more, input);
	const until = el("td", "", row.until);
	if (row.state) until.append(` ${row.state === "expired" ? "просрочен" : "скоро"}`);
	if (row.spoil) {
		const spoil = el("button", "", "Списать просроченное");
		spoil.addEventListener("click", () => write({ op: "spoil", item: row.item, unit: row.unit }));
		until.append(" ", spoil);
	}
	tr.append(el("td", "", row.item), left, until);
	return tr;
}

function foodRow(food) {
	const item = el("li", "agi");
	item.append(el("span", "tm", food.logged_at.slice(11, 16)), el("span", "ttl", food.text));
	if (food.kcal !== null) item.append(el("span", "st", `${Math.round(food.kcal)} ккал`));
	return item;
}

function renderPantry(view, today) {
	const rows = pantryRows(view, today);
	node("pantry-rows").replaceChildren(...rows.map(rowNode));
	node("pantry-empty").hidden = rows.length > 0;
	node("food-left").textContent = remainingText(view);
	node("food-empty").hidden = view.food.length > 0;
	node("food-list").replaceChildren(...view.food.map(foodRow));
}

// Загрузить кладовую дня day и показать на вкладке; today — настоящий день (кнопка списания).
export async function loadPantry(day, today) {
	current = { day, today };
	try {
		const response = await fetch(`/api/pantry?date=${day}`);
		if (!response.ok) throw new Error(await response.text());
		renderPantry(await response.json(), today);
	} catch (error) {
		showNote(`Не удалось загрузить: ${error.message}`);
	}
}

function pickUnit(value) {
	unit = value;
	for (const button of node("pantry-units").children) {
		button.setAttribute("aria-pressed", String(button.dataset.unit === unit));
	}
}

async function addProduct(event) {
	event.preventDefault();
	const qty = Number(node("pantry-qty").value.replace(",", "."));
	const payload = { op: "add", item: node("pantry-name").value, qty, unit };
	const until = node("pantry-until").value;
	if (until) payload.until = until;
	if (!(await write(payload))) return;
	node("pantry-form").reset();
	node("pantry-form").hidden = true;
}

if (typeof document !== "undefined") {
	for (const value of UNITS) {
		const button = el("button", "", value);
		button.type = "button";
		button.dataset.unit = value;
		button.addEventListener("click", () => pickUnit(value));
		node("pantry-units").append(button);
	}
	pickUnit("g");
	node("pantry-add").addEventListener("click", () => {
		node("pantry-form").hidden = false;
		node("pantry-name").focus();
	});
	node("pantry-form").addEventListener("submit", addProduct);
	node("pantry-form").addEventListener("keydown", (event) => {
		if (event.key === "Escape") node("pantry-form").hidden = true;
	});
}

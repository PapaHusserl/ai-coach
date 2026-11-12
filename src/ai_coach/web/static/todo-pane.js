// Пульт: карточка «Туду» на вкладке «План», только DOM (зовётся в браузере). Чистые функции — todo-model.js.

import { el } from "./dom.js";
import { closeEventForm, openEventForm } from "./event-form.js";
import { postJson } from "./post.js";
import { moveButtons, todoPayload, todoRows, todoSpan } from "./todo-model.js";
import { toast } from "./toast.js";

let busy = false;
let editing = null; // id пункта в правке — таймер его не перерисовывает
let moving = null; // id пункта, для которого открыта форма переноса в календарь
let moveBox = null; // её узел: живёт между перерисовками списка
let movingDay = null; // день, на который открыта форма переноса
let kept = ""; // текст после переноса, пока не начато другое действие
let reloadDay = () => {}; // перечитать день пульта после переноса

function node(id) {
	return document.getElementById(id);
}

function showError(text) {
	const note = node("todo-error");
	note.textContent = text;
	note.hidden = !text;
}

// Занято: идёт запись, открыта форма (правка или «+ задача») или фокус в поле карточки —
// таймер её не перерисовывает.
export function todoBusy() {
	const card = node("todo-card");
	const active = document.activeElement;
	const typing = card.contains(active) && ["INPUT", "TEXTAREA"].includes(active.tagName);
	const open = editing !== null || moving !== null || !node("todo-form").hidden;
	return busy || open || typing;
}

async function write(payload, done = "Записано") {
	busy = true;
	kept = "";
	showError("");
	const result = await postJson("/api/todo", payload);
	busy = false;
	if (!result.ok) {
		showError(result.text);
		return false;
	}
	toast(done);
	editing = null;
	await loadTodo();
	return true;
}

function editNode(row) {
	const form = el("form", "pf");
	const title = el("input");
	title.value = row.title;
	title.setAttribute("aria-label", "Название");
	const note = el("input");
	note.value = row.note;
	note.placeholder = "Заметка";
	note.setAttribute("aria-label", "Заметка");
	const save = el("button", "", "Сохранить");
	const cancel = el("button", "", "Отмена");
	cancel.type = "button";
	cancel.addEventListener("click", () => {
		editing = null;
		loadTodo();
	});
	form.addEventListener("submit", (event) => {
		event.preventDefault();
		write(todoPayload("edit", { id: row.id, title: title.value, note: note.value }));
	});
	form.append(title, note, save, cancel);
	return form;
}

// Перенос в календарь (Р5): форма пункта шкалы, kind task, состояние туду не меняется (Р6).
function toCalendar(row) {
	const now = new Date();
	const day = document.body.dataset.day;
	moving = row.id;
	movingDay = day;
	editing = null; // открыта одна форма
	kept = "";
	showError("");
	moveBox = el("div", "sform");
	openEventForm(moveBox, {
		day,
		span: todoSpan(now, day),
		title: row.title,
		fixedKind: "task",
		fail: showError,
		onDone: () => {
			moving = null;
			moveBox = null;
			kept = node("todo-error").textContent; // «записан черновиком» переживает перерисовку
			reloadDay();
		},
	});
	// Форма собрана вне списка: ставим её под строку и возвращаем фокус в название.
	loadTodo().then(() => moveBox?.querySelector("input.wide")?.focus());
}

function rowNode(row) {
	const item = el("li", `agi todo ${row.state}`);
	const head = el("div", "agh");
	head.append(el("span", "tm", row.state === "doing" ? "в работе" : ""), el("span", "ttl", row.title));
	item.append(head);
	if (row.note) item.append(el("div", "hint", row.note));
	if (editing === row.id) {
		item.append(editNode(row));
		return item;
	}
	const actions = el("div", "frow");
	const edit = el("button", "link", "править");
	edit.type = "button";
	edit.addEventListener("click", () => {
		editing = row.id;
		moving = null; // открыта одна форма
		moveBox = null;
		loadTodo();
	});
	const calendar = el("button", "link", "в календарь");
	calendar.type = "button";
	calendar.addEventListener("click", () => toCalendar(row));
	actions.append(edit, calendar);
	for (const move of moveButtons(row.state)) {
		const button = el("button", "", move.label);
		button.type = "button";
		button.addEventListener("click", () =>
			write(todoPayload("move", { id: row.id, state: move.state }), `#${row.id} -> ${move.state}`),
		);
		actions.append(button);
	}
	item.append(actions);
	if (moving === row.id) item.append(moveBox);
	return item;
}

function renderTodo(view) {
	const rows = todoRows(view);
	if (editing !== null && !rows.some((row) => row.id === editing)) editing = null;
	// Смена дня или исчезновение пункта закрывает форму переноса: событие ушло бы на прежний день (как в renderScale).
	if (moving !== null && (movingDay !== document.body.dataset.day || !rows.some((row) => row.id === moving))) {
		closeEventForm(moveBox);
		moving = null;
		moveBox = null;
		kept = "";
	}
	showError(view.error ?? kept);
	node("todo-rows").replaceChildren(...rows.map(rowNode));
	node("todo-empty").hidden = rows.length > 0;
}

// Загрузить открытые пункты и показать карточку.
export async function loadTodo(reload) {
	if (reload) reloadDay = reload;
	try {
		const response = await fetch("/api/todo");
		if (!response.ok) throw new Error(await response.text());
		renderTodo(await response.json());
	} catch (error) {
		showError(`Не удалось загрузить: ${error.message}`);
	}
}

async function addTask(event) {
	event.preventDefault();
	const payload = todoPayload("add", { title: node("todo-title").value, note: node("todo-note").value });
	if (!(await write(payload))) return;
	node("todo-form").reset();
	node("todo-form").hidden = true;
}

if (typeof document !== "undefined") {
	node("todo-add").addEventListener("click", () => {
		node("todo-form").hidden = false;
		node("todo-title").focus();
	});
	node("todo-form").addEventListener("submit", addTask);
	node("todo-form").addEventListener("keydown", (event) => {
		if (event.key === "Escape") node("todo-form").hidden = true;
	});
}

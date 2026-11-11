// Пульт: карточка «Туду» на вкладке «План», только DOM (зовётся в браузере). Чистые функции — todo-model.js.

import { el } from "./dom.js";
import { postJson } from "./post.js";
import { moveButtons, todoPayload, todoRows } from "./todo-model.js";
import { toast } from "./toast.js";

let busy = false;
let editing = null; // id пункта в правке — таймер его не перерисовывает

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
	return (
		busy ||
		editing !== null ||
		!node("todo-form").hidden ||
		(card.contains(active) && ["INPUT", "TEXTAREA"].includes(active.tagName))
	);
}

async function write(payload, done = "Записано") {
	busy = true;
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
		loadTodo();
	});
	actions.append(edit);
	for (const move of moveButtons(row.state)) {
		const button = el("button", "", move.label);
		button.type = "button";
		button.addEventListener("click", () =>
			write(todoPayload("move", { id: row.id, state: move.state }), `#${row.id} -> ${move.state}`),
		);
		actions.append(button);
	}
	item.append(actions);
	return item;
}

function renderTodo(view) {
	showError(view.error ?? "");
	const rows = todoRows(view);
	node("todo-rows").replaceChildren(...rows.map(rowNode));
	node("todo-empty").hidden = rows.length > 0;
}

// Загрузить открытые пункты и показать карточку.
export async function loadTodo() {
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

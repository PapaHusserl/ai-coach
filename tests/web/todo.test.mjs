import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
	moveButtons,
	todoPayload,
	todoRows,
	todoSpan,
} from "../../src/ai_coach/web/static/todo-model.js";

const item = (id, state) => ({ id, title: `T${id}`, note: "", state });

// MOVES из workload/todo.py (источник правды): состояние -> [куда можно]
function pyMoves() {
	const text = readFileSync(new URL("../../src/ai_coach/workload/todo.py", import.meta.url), "utf8");
	const block = text.slice(text.indexOf("MOVES"), text.indexOf("}", text.indexOf("MOVES")));
	const moves = {};
	for (const m of block.matchAll(/"(\w+)": \(([^)]*)\)/g)) {
		moves[m[1]] = [...m[2].matchAll(/"(\w+)"/g)].map((x) => x[1]);
	}
	return moves;
}

test("todoRows: doing первыми, затем по id", () => {
	const rows = todoRows({ items: [item(3, "todo"), item(1, "todo"), item(5, "doing"), item(2, "doing")] });
	assert.deepEqual(rows.map((row) => row.id), [2, 5, 1, 3]);
});

test("todoRows: закрытые, если пришли, отбрасываются", () => {
	const rows = todoRows({ items: [item(1, "done"), item(2, "todo"), item(3, "dropped")] });
	assert.deepEqual(rows.map((row) => row.id), [2]);
});

test("todoRows: пустой список — пусто", () => {
	assert.deepEqual(todoRows({ items: [] }), []);
});

test("moveButtons: todo — как MOVES", () => {
	assert.deepEqual(moveButtons("todo").map((b) => b.state), pyMoves().todo);
});

test("moveButtons: doing — как MOVES", () => {
	assert.deepEqual(moveButtons("doing").map((b) => b.state), pyMoves().doing);
});

test("moveButtons: todo — три кнопки с подписями", () => {
	assert.deepEqual(moveButtons("todo").map((b) => b.label), ["в работу", "сделано", "отбросить"]);
});

test("moveButtons: doing — подписи", () => {
	assert.deepEqual(moveButtons("doing").map((b) => b.label), ["в список", "сделано", "отбросить"]);
});

test("moveButtons: у закрытых пусто (Р3 = 2)", () => {
	assert.deepEqual(moveButtons("done"), []);
	assert.deepEqual(moveButtons("dropped"), []);
});

test("todoPayload: add", () => {
	assert.deepEqual(todoPayload("add", { title: "Х", note: "н" }), { op: "add", title: "Х", note: "н" });
});

test("todoPayload: edit", () => {
	assert.deepEqual(todoPayload("edit", { id: 4, title: "Х", note: "н" }), {
		op: "edit",
		id: 4,
		title: "Х",
		note: "н",
	});
});

test("todoPayload: move", () => {
	assert.deepEqual(todoPayload("move", { id: 4, state: "done" }), { op: "move", id: 4, state: "done" });
});

const at = (h, m) => new Date(2026, 10, 11, h, m, 0);

test("todoSpan: сегодня 10:07 — 10:10–10:40 (Р5а)", () => {
	assert.deepEqual(todoSpan(at(10, 7), "2026-11-11"), { start: 610, end: 640 });
});

test("todoSpan: сегодня 23:50 — 23:30–24:00 как newSpan", () => {
	assert.deepEqual(todoSpan(at(23, 50), "2026-11-11"), { start: 1410, end: 1440 });
});

test("todoSpan: другой день — 12:00–12:30", () => {
	assert.deepEqual(todoSpan(at(10, 7), "2026-11-12"), { start: 720, end: 750 });
});

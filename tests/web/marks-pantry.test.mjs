// Срок жизни строк о списанном (П8, Р3 = 1): стоят до закрытия окна. Отдельный файл: нужен document до загрузки
// marks.js, а marks.test.mjs грузит его без DOM.
import test from "node:test";
import assert from "node:assert/strict";

class FakeNode {
	constructor(tag) {
		this.tag = tag;
		this.textContent = "";
		this.children = [];
		this.listeners = {};
		this.classList = { toggle() {}, add() {}, remove() {} };
	}
	append(...nodes) {
		this.children.push(...nodes);
	}
	replaceChildren(...nodes) {
		this.children = nodes;
	}
	remove() {}
	setAttribute() {}
	addEventListener(name, handler) {
		(this.listeners[name] ??= []).push(handler);
	}
	click() {
		for (const handler of this.listeners.click ?? []) handler();
	}
}

globalThis.document = { createElement: (tag) => new FakeNode(tag), body: new FakeNode("body") };
globalThis.setTimeout = () => 0;
globalThis.clearTimeout = () => {};

const { mountMarks, unmountMarks, setupMarks } = await import("../../src/ai_coach/web/static/marks.js");

const DAY = "2026-11-08";
const ITEM = { what: "рис", qty: "150 г", kcal: 1, protein_g: 1, fat_g: 1, carbs_g: 1 };
const PANTRY = { used: ["рис 150 г"], skipped: [], warnings: [] };
const marks = { ratings: [], feel: [], slips: [], food: [], done: null };
const row = {
	id: 1,
	kind: "meal",
	start_at: `${DAY}T08:00:00`,
	end_at: `${DAY}T09:00:00`,
	due: false,
	marks,
	meal: { remaining: null, food: [], offers: [{ id: 7, name: "Рис", items: [ITEM] }] },
};
const view = { date: DAY, now: `${DAY}T08:30:00` };

function walk(node) {
	return [node, ...node.children.flatMap(walk)];
}

function find(root, tag, text) {
	const found = walk(root).find((n) => n.tag === tag && n.textContent === text);
	assert.ok(found, `${tag} «${text}» не найден`);
	return found;
}

function paragraphs(root) {
	return walk(root)
		.filter((n) => n.tag === "p")
		.map((n) => n.textContent);
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

// Окно еды открыто, «Съел это» нажато, ответ сервера со строками о списанном.
async function opened(replies) {
	const queue = [...replies];
	globalThis.fetch = async () => ({ ok: true, status: 200, text: async () => JSON.stringify(queue.shift()) });
	setupMarks(async () => {});
	const item = new FakeNode("li");
	mountMarks(item, row, view);
	find(item, "button", "Съел это").click();
	await settle();
	return item;
}

const LINE = "Списано из кладовой: рис 150 г.";

test("после «Съел вариант» строки о списанном стоят в окне", async () => {
	const item = await opened([{ id: 5, pantry: PANTRY }]);
	assert.ok(paragraphs(item).includes(LINE));
	unmountMarks();
});

test("запись «своё» в том же окне строк о списанном не стирает", async () => {
	const item = await opened([{ id: 5, pantry: PANTRY }, { id: 6 }]);
	const text = walk(item).find((n) => n.tag === "textarea");
	text.value = "борщ";
	for (const handler of text.listeners.input) handler();
	find(item, "button", "Записать своё").click();
	await settle();
	assert.ok(walk(item).some((n) => n.textContent === LINE));
	unmountMarks();
});

test("запись «Срыв» в том же окне строк о списанном не стирает", async () => {
	const item = await opened([{ id: 5, pantry: PANTRY }, { id: 6 }]);
	find(item, "button", "Срыв").click();
	const text = walk(item).find((n) => n.tag === "textarea");
	text.value = "печенье";
	for (const handler of text.listeners.input) handler();
	find(item, "button", "Сохранить").click();
	await settle();
	find(item, "button", "Что съел").click();
	assert.ok(walk(item).some((n) => n.textContent === LINE));
	unmountMarks();
});

test("переход на другую вкладку и обратно — строки на месте", async () => {
	const item = await opened([{ id: 5, pantry: PANTRY }]);
	find(item, "button", "Срыв").click();
	find(item, "button", "Что съел").click();
	assert.ok(walk(item).some((n) => n.textContent === LINE));
	unmountMarks();
});

test("второй «Съел вариант» в том же окне заменяет строки прежнего", async () => {
	const second = { used: ["яйцо 2 шт"], skipped: [], warnings: [] };
	const item = await opened([
		{ id: 5, pantry: PANTRY },
		{ id: 6, pantry: second },
	]);
	find(item, "button", "Съел это").click();
	await settle();
	const lines = paragraphs(item);
	assert.ok(lines.includes("Списано из кладовой: яйцо 2 шт."));
	assert.ok(!lines.includes(LINE));
	unmountMarks();
});

test("закрыть и открыть окно — строк нет", async () => {
	await opened([{ id: 5, pantry: PANTRY }]);
	unmountMarks();
	const again = new FakeNode("li");
	mountMarks(again, row, view);
	assert.ok(!walk(again).some((n) => n.textContent === LINE));
	unmountMarks();
});

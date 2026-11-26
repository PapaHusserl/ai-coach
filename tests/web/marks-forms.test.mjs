// Окно пункта с формой тренера и вкладки окна (Н48, BACKLOG 127). Отдельный файл: нужен document до загрузки
// marks.js (см. marks-intake.test.mjs). Данные вымышленные: форма temp, день 2026-11-08.
import test from "node:test";
import assert from "node:assert/strict";

class FakeNode {
	constructor(tag) {
		this.tag = tag;
		this.textContent = "";
		this.className = "";
		this.value = "";
		this.children = [];
		this.listeners = {};
		this.attrs = {};
		this.classList = { toggle() {}, add() {}, remove() {} };
	}
	append(...nodes) {
		this.children.push(...nodes);
	}
	replaceChildren(...nodes) {
		this.children = nodes;
	}
	remove() {}
	setAttribute(name, value) {
		this.attrs[name] = String(value);
	}
	addEventListener(name, handler) {
		(this.listeners[name] ??= []).push(handler);
	}
	fire(name) {
		for (const handler of this.listeners[name] ?? []) handler();
	}
	click() {
		this.fire("click");
	}
}

globalThis.document = { createElement: (tag) => new FakeNode(tag), body: new FakeNode("body") };
globalThis.setTimeout = () => 0;
globalThis.clearTimeout = () => {};

const { mountMarks, unmountMarks, setupMarks } = await import("../../src/ai_coach/web/static/marks.js");

const DAY = "2026-11-08";
const FORM = {
	title: "Температура",
	fields: [
		{ key: "score", type: "scale", label: "Самочувствие" },
		{ key: "temperature", type: "number", label: "Температура", unit: "°C" },
		{ key: "fever", type: "yesno", label: "Озноб", required: false },
	],
};
const marks = { ratings: [], feel: [], slips: [], food: [], done: null };

const walk = (node) => [node, ...node.children.flatMap(walk)];
const buttons = (root) => walk(root).filter((n) => n.tag === "button");
const settle = () => new Promise((resolve) => setImmediate(resolve));
const tabNames = (item) => walk(item).filter((n) => n.className === "tab").map((n) => n.textContent);
const saveButton = (item) => walk(item).find((n) => n.className === "save");
const labels = (item) => walk(item).map((n) => n.textContent);

// Строка шкалы по подписи: узел, у которого первый потомок — подпись, а среди потомков есть ряд кнопок «qs».
const scaleRow = (item, label) =>
	walk(item).find((n) => n.children[0]?.textContent === label && n.children.some((c) => c.className === "qs"));
const clickScale = (item, label, value) =>
	buttons(scaleRow(item, label)).find((b) => b.textContent === String(value)).click();

// Открыть окно пункта; id у каждого теста свой — черновики окна живут по «день:id».
function open(id, extra, fetchLog = []) {
	globalThis.fetch = async (url, init) => {
		if (String(url).startsWith("/api/screen")) return { ok: false, status: 404, text: async () => "" };
		fetchLog.push({ url, body: JSON.parse(init.body) });
		return { ok: true, status: 200, text: async () => "{}" };
	};
	setupMarks(async () => {});
	const item = new FakeNode("li");
	const row = {
		id,
		kind: "checkin",
		survey: null,
		start_at: `${DAY}T08:00:00`,
		end_at: `${DAY}T09:00:00`,
		due: false,
		marks,
		form: null,
		...extra,
	};
	mountMarks(item, row, { date: DAY, now: `${DAY}T08:30:00` });
	return item;
}

const withForm = { survey: "form:temp", form: FORM };

// --- чек-ин с формой ---

test("чек-ин с формой: вкладка одна, подпись — название формы", () => {
	const item = open(1, withForm);
	unmountMarks();
	assert.deepEqual(tabNames(item), ["Температура"]);
});

test("чек-ин с формой: подписи полей, единица и полюса шкалы", () => {
	const item = open(2, withForm);
	unmountMarks();
	const all = labels(item);
	for (const text of ["Самочувствие", "Температура", "Озноб", "°C", "плохо — отлично"]) {
		assert.ok(all.includes(text), text);
	}
});

test("чек-ин с формой: «Сохранить» выключена, после шкалы — ещё выключена, после числа — включена", () => {
	const item = open(3, withForm);
	assert.equal(saveButton(item).disabled, true);
	clickScale(item, "Самочувствие", 4);
	assert.equal(saveButton(item).disabled, true);
	const input = walk(item).find((n) => n.tag === "input");
	input.value = "37,2";
	input.fire("input");
	unmountMarks();
	assert.equal(saveButton(item).disabled, false);
});

test("чек-ин с формой: «Сохранить» шлёт один POST /api/mark с values формы", async () => {
	const log = [];
	const item = open(4, withForm, log);
	clickScale(item, "Самочувствие", 4);
	const input = walk(item).find((n) => n.tag === "input");
	input.value = "37,2";
	input.fire("input");
	saveButton(item).click();
	await settle();
	unmountMarks();
	assert.equal(log.length, 1);
	assert.ok(log[0].url.endsWith("/api/mark"));
	assert.deepEqual(log[0].body, {
		event_id: 4,
		date: DAY,
		mark: "form",
		values: { score: 4, temperature: 37.2 },
	});
});

// --- задача с формой ---

test("задача с формой: вкладки по порядку, форма последняя", () => {
	const item = open(5, { kind: "task", ...withForm });
	unmountMarks();
	assert.deepEqual(tabNames(item), ["Оценка", "Самочувствие", "Срыв", "Температура"]);
});

test("задача: survey form:нет и form null — вкладки формы нет, окно собирается", () => {
	const item = open(6, { kind: "task", survey: "form:нет", form: null });
	unmountMarks();
	assert.deepEqual(tabNames(item), ["Оценка", "Самочувствие", "Срыв"]);
});

test("задача с формой: клик по вкладке формы — поля видны, «Сохранить» выключена", () => {
	const item = open(7, { kind: "task", ...withForm });
	const tab = walk(item).find((n) => n.className === "tab" && n.textContent === "Температура");
	tab.click();
	unmountMarks();
	assert.ok(labels(item).includes("Озноб"));
	assert.equal(saveButton(item).disabled, true);
});

// --- другие вкладки окна ---

test("вкладка «Оценка»: «Сохранить» выключена, после трёх обязательных шкал — включена", () => {
	const item = open(8, { kind: "focus" });
	assert.equal(saveButton(item).disabled, true);
	clickScale(item, "Фокус", 3);
	clickScale(item, "Усталость", 3);
	assert.equal(saveButton(item).disabled, true);
	clickScale(item, "Усилие", 3);
	unmountMarks();
	assert.equal(saveButton(item).disabled, false);
});

test("вечерний чек-ин: вкладка «Чек-ин», восемь шкал, три поля часов и «Погружение»", () => {
	const item = open(9, {});
	unmountMarks();
	assert.deepEqual(tabNames(item), ["Чек-ин"]);
	const all = labels(item);
	const scales = [
		"Самочувствие",
		"Настроение",
		"Стресс",
		"Усталость",
		"Раздражительность",
		"Мысли о работе вечером",
		"Помехи",
		"Ценность сделанного",
	];
	for (const text of [...scales, "Работа, ч", "Хобби, ч", "Отдых, ч", "Погружение"]) {
		assert.ok(all.includes(text), text);
	}
});

test("вечерний чек-ин: «Сохранить» выключена, после «Самочувствие» — включена", () => {
	const item = open(10, {});
	assert.equal(saveButton(item).disabled, true);
	clickScale(item, "Самочувствие", 4);
	unmountMarks();
	assert.equal(saveButton(item).disabled, false);
});

test("WHO-5: вкладка «WHO-5», «Сохранить» выключена, после пяти ответов — включена", () => {
	const item = open(11, { survey: "who5", who5: null });
	assert.deepEqual(tabNames(item), ["WHO-5"]);
	assert.equal(saveButton(item).disabled, true);
	const rows = walk(item).filter((n) => n.className === "w5row");
	assert.equal(rows.length, 5);
	for (const [index, line] of rows.entries()) {
		assert.equal(saveButton(item).disabled, true, `до ответа ${index + 1}`);
		buttons(line).find((b) => b.textContent === "3").click();
	}
	unmountMarks();
	assert.equal(saveButton(item).disabled, false);
});

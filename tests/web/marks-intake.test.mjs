// Блок «Добавки к приёму» (П8, партия 2, Р7–Р18). Отдельный файл: нужен document до загрузки marks.js и
// intake-pane.js (см. marks-pantry.test.mjs).
import test from "node:test";
import assert from "node:assert/strict";

class FakeNode {
	constructor(tag) {
		this.tag = tag;
		this.textContent = "";
		this.className = "";
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
	click() {
		for (const handler of this.listeners.click ?? []) handler();
	}
}

globalThis.document = { createElement: (tag) => new FakeNode(tag), body: new FakeNode("body") };
globalThis.setTimeout = () => 0;
globalThis.clearTimeout = () => {};

const { intakeRows, intakeBlock } = await import("../../src/ai_coach/web/static/intake-pane.js");
const { mountMarks, unmountMarks, setupMarks } = await import("../../src/ai_coach/web/static/marks.js");

const D_VIT = { kind: "med", id: 3, name: "Витамин D", dose: 2000.0, unit: "iu", time_note: "утром", taken: false };
const CREATINE = { kind: "supplement", id: 1, name: "Креатин", dose: 5.0, unit: "g", time_note: null, taken: false };
const texts = (rows) => rows.map((row) => row.text);

function walk(node) {
	return [node, ...node.children.flatMap(walk)];
}

const buttons = (root) => walk(root).filter((n) => n.tag === "button");

// --- intakeRows ---

test("intakeRows: «имя · доза единица · когда»", () => {
	assert.deepEqual(texts(intakeRows({ intake: [D_VIT] })), ["Витамин D · 2000 iu · утром"]);
});

test("intakeRows: строка без «когда» — без хвоста и разделителя в конце", () => {
	const [text] = texts(intakeRows({ intake: [CREATINE] }));
	assert.equal(text, "Креатин · 5 g");
});

test("intakeRows: доза как :g — 2000, не 2000.0; 0.5", () => {
	const half = { ...D_VIT, dose: 0.5, unit: "mg", time_note: null };
	assert.deepEqual(texts(intakeRows({ intake: [D_VIT, half] })), ["Витамин D · 2000 iu · утром", "Витамин D · 0.5 mg"]);
});

test("intakeRows: единицы как в coach med list, без русских «МЕ» и «мг»", () => {
	const units = ["iu", "mg", "mcg", "g", "ml", "pcs"];
	const rows = intakeRows({ intake: units.map((unit, i) => ({ ...CREATINE, id: i, unit, dose: 1 })) });
	assert.deepEqual(texts(rows), units.map((unit) => `Креатин · 1 ${unit}`));
});

test("intakeRows: принятое — «✓ » перед именем", () => {
	assert.deepEqual(texts(intakeRows({ intake: [{ ...D_VIT, taken: true }] })), ["✓ Витамин D · 2000 iu · утром"]);
});

test("intakeRows: порядок строк как пришёл", () => {
	assert.deepEqual(texts(intakeRows({ intake: [D_VIT, CREATINE] })), ["Витамин D · 2000 iu · утром", "Креатин · 5 g"]);
});

test("intakeRows: нет курсов и добавок — пусто", () => {
	assert.deepEqual(intakeRows({ intake: [] }), []);
});

// --- intakeBlock ---

test("intakeBlock: нет строк — блока нет, заголовка тоже", () => {
	assert.equal(intakeBlock({ intake: [] }, () => {}), null);
});

test("intakeBlock: заголовок «Добавки к приёму» и строка-кнопка на позицию", () => {
	const block = intakeBlock({ intake: [D_VIT, CREATINE] }, () => {});
	assert.ok(walk(block).some((n) => n.textContent === "Добавки к приёму"));
	assert.equal(buttons(block).length, 2);
});

test("intakeBlock: aria-pressed true и «✓ » у принятого, false и без «✓ » у непринятого", () => {
	const block = intakeBlock({ intake: [{ ...D_VIT, taken: true }, CREATINE] }, () => {});
	const [taken, free] = buttons(block);
	assert.equal(taken.attrs["aria-pressed"], "true");
	assert.equal(taken.textContent, "✓ Витамин D · 2000 iu · утром");
	assert.equal(free.attrs["aria-pressed"], "false");
	assert.equal(free.textContent, "Креатин · 5 g");
});

test("intakeBlock: клик по непринятому — onToggle с taken 1", () => {
	const calls = [];
	const block = intakeBlock({ intake: [D_VIT] }, (...args) => calls.push(args));
	buttons(block)[0].click();
	assert.equal(calls.length, 1);
	assert.equal(calls[0][0].kind, "med");
	assert.equal(calls[0][0].id, 3);
	assert.equal(Number(calls[0][1]), 1);
});

test("intakeBlock: клик по принятому — onToggle с taken 0", () => {
	const calls = [];
	const block = intakeBlock({ intake: [{ ...D_VIT, taken: true }] }, (...args) => calls.push(args));
	buttons(block)[0].click();
	assert.equal(Number(calls[0][1]), 0);
});

test("intakeBlock: будущий день (onToggle нет) — строки текстом, кнопок нет", () => {
	const block = intakeBlock({ intake: [D_VIT, CREATINE] }, null);
	assert.equal(buttons(block).length, 0);
	const all = walk(block).map((n) => n.textContent);
	assert.ok(all.includes("Витамин D · 2000 iu · утром"));
	assert.ok(all.includes("Креатин · 5 g"));
});

// --- в окне еды ---

const DAY = "2026-11-08";
const marks = { ratings: [], feel: [], slips: [], food: [], done: null };
const row = {
	id: 1,
	kind: "meal",
	start_at: `${DAY}T08:00:00`,
	end_at: `${DAY}T09:00:00`,
	due: false,
	marks,
	meal: { remaining: null, food: [], offers: [], intake: [D_VIT, CREATINE] },
};

function opened(now, fetchLog = []) {
	globalThis.fetch = async (url, init) => {
		fetchLog.push({ url, body: JSON.parse(init.body) });
		return { ok: true, status: 200, text: async () => "{}" };
	};
	setupMarks(async () => {});
	const item = new FakeNode("li");
	mountMarks(item, row, { date: DAY, now: `${DAY}T${now}` });
	return item;
}

test("окно еды: блок стоит первым — над «Записано ✓»", () => {
	const item = opened("08:30:00");
	unmountMarks();
	const order = walk(item);
	const head = order.findIndex((n) => n.textContent === "Добавки к приёму");
	const saved = order.findIndex((n) => n.className === "saved");
	assert.ok(head >= 0 && saved >= 0);
	assert.ok(head < saved);
});

test("окно еды: клик по строке шлёт POST /api/intake с kind, item_id, date, taken", async () => {
	const log = [];
	const item = opened("08:30:00", log);
	buttons(item).find((n) => n.textContent === "Витамин D · 2000 iu · утром").click();
	await new Promise((resolve) => setImmediate(resolve));
	unmountMarks();
	assert.equal(log.length, 1);
	assert.ok(log[0].url.endsWith("/api/intake"));
	assert.deepEqual({ ...log[0].body, taken: Number(log[0].body.taken) }, { kind: "med", item_id: 3, date: DAY, taken: 1 });
});

// Окно еды, когда отмечать (Р12 = 1): сегодня (и до начала пункта) и прошлые дни — кнопки, будущий день — текст.
const D_VIT_TEXT = "Витамин D · 2000 iu · утром";
const shiftDay = (days) => new Date(Date.parse(`${DAY}T12:00:00Z`) + days * 86400000).toISOString().slice(0, 10);
const withOffer = { ...row.meal, offers: [{ id: 7, name: "Рис", items: [] }] };

function openedOn(day, now, fetchLog = []) {
	globalThis.fetch = async (url, init) => {
		fetchLog.push({ url, body: JSON.parse(init.body) });
		return { ok: true, status: 200, text: async () => "{}" };
	};
	setupMarks(async () => {});
	const item = new FakeNode("li");
	const dayRow = { ...row, start_at: `${day}T08:00:00`, end_at: `${day}T09:00:00`, meal: withOffer };
	mountMarks(item, dayRow, { date: day, now: `${DAY}T${now}` });
	return item;
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

test("окно еды: сегодня до начала пункта — строки-кнопки, клик шлёт POST /api/intake с taken 1", async () => {
	const log = [];
	const item = openedOn(DAY, "07:00:00", log);
	const button = buttons(item).find((n) => n.textContent === D_VIT_TEXT);
	assert.ok(button, "строка блока должна быть кнопкой");
	button.click();
	await settle();
	unmountMarks();
	assert.equal(log.length, 1);
	assert.ok(log[0].url.endsWith("/api/intake"));
	assert.deepEqual({ ...log[0].body, taken: Number(log[0].body.taken) }, { kind: "med", item_id: 3, date: DAY, taken: 1 });
});

test("окно еды: сегодня до начала пункта — «Съел» у пункта по-прежнему нет (Р36)", () => {
	const item = openedOn(DAY, "07:00:00");
	unmountMarks();
	assert.ok(!buttons(item).some((n) => n.textContent.startsWith("Съел")));
});

test("окно еды: завтра — блок виден, строк-кнопок нет, ничего не шлётся", async () => {
	const log = [];
	const item = openedOn(shiftDay(1), "07:00:00", log);
	const all = walk(item).map((n) => n.textContent);
	assert.ok(all.includes("Добавки к приёму"));
	assert.ok(all.includes(D_VIT_TEXT));
	assert.ok(!buttons(item).some((n) => n.textContent === D_VIT_TEXT));
	await settle();
	unmountMarks();
	assert.deepEqual(log, []);
});

test("окно еды: прошедший день — строки-кнопки, клик шлёт POST с датой того дня", async () => {
	const log = [];
	const yesterday = shiftDay(-1);
	const item = openedOn(yesterday, "07:00:00", log);
	const button = buttons(item).find((n) => n.textContent === D_VIT_TEXT);
	assert.ok(button, "строка блока должна быть кнопкой");
	button.click();
	await settle();
	unmountMarks();
	assert.equal(log.length, 1);
	assert.equal(log[0].body.date, yesterday);
});

// Отметка не записалась (Р22 = 1): всплывашка; нет связи — «Не сохранилось, нет связи с пультом»,
// отказ сервера (400) — его текст, остальное — «Не сохранилось, ошибка пульта (код N)».
const toastText = () => globalThis.document.body.children.findLast((n) => n.className === "toast")?.textContent;

async function clickWith(fetchImpl) {
	const reloads = [];
	globalThis.fetch = fetchImpl;
	const quiet = console.error;
	console.error = () => {};
	setupMarks(async () => reloads.push(1));
	const item = new FakeNode("li");
	mountMarks(item, row, { date: DAY, now: `${DAY}T08:30:00` });
	buttons(item).find((n) => n.textContent === D_VIT_TEXT).click();
	await settle();
	unmountMarks();
	console.error = quiet;
	return reloads;
}

test("отметка не записалась: нет связи — всплывашка «Не сохранилось, нет связи с пультом», день не перечитан", async () => {
	const reloads = await clickWith(async () => {
		throw new TypeError("fetch failed");
	});
	assert.equal(toastText(), "Не сохранилось, нет связи с пультом");
	assert.deepEqual(reloads, []);
});

test("отметка не записалась: отказ сервера 400 — его текст во всплывашке", async () => {
	const reloads = await clickWith(async () => ({
		ok: false,
		status: 400,
		text: async () => "Такой позиции в блоке этого дня нет.",
	}));
	assert.equal(toastText(), "Такой позиции в блоке этого дня нет.");
	assert.deepEqual(reloads, []);
});

test("отметка не записалась: код 500 — «Не сохранилось, ошибка пульта (код 500)»", async () => {
	await clickWith(async () => ({ ok: false, status: 500, text: async () => "boom" }));
	assert.equal(toastText(), "Не сохранилось, ошибка пульта (код 500)");
});

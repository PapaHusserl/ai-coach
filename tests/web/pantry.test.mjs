import test from "node:test";
import assert from "node:assert/strict";
import { pantryRows, parseDelta, stepFor } from "../../src/ai_coach/web/static/pantry-model.js";

test("stepFor: шаг по единице (Р6 = 1)", () => {
	assert.equal(stepFor("g"), 50);
	assert.equal(stepFor("ml"), 100);
	assert.equal(stepFor("pcs"), 1);
});

test("parseDelta: «+200» — добавить", () => {
	assert.deepEqual(parseDelta("+200"), { op: "add", qty: 200 });
});

test("parseDelta: «-50» — списать", () => {
	assert.deepEqual(parseDelta("-50"), { op: "use", qty: 50 });
});

test("parseDelta: число без знака — сверка", () => {
	assert.deepEqual(parseDelta("120"), { op: "set", qty: 120 });
});

test("parseDelta: пробелы по краям не мешают", () => {
	assert.deepEqual(parseDelta("  +200 "), { op: "add", qty: 200 });
});

test("parseDelta: дробное число", () => {
	assert.deepEqual(parseDelta("+2.5"), { op: "add", qty: 2.5 });
});

test("parseDelta: «0» — сверка до нуля", () => {
	assert.deepEqual(parseDelta("0"), { op: "set", qty: 0 });
});

test("parseDelta: «+0» и «-0» — null", () => {
	assert.equal(parseDelta("+0"), null);
	assert.equal(parseDelta("-0"), null);
});

const row = (fields) => ({
	item: "рис",
	qty: 500,
	unit: "g",
	expires_on: null,
	opened: 0,
	expired: false,
	soon: false,
	...fields,
});

test("pantryRows: строка без срока", () => {
	const [r] = pantryRows({ rows: [row({})] }, "2026-11-07");
	assert.deepEqual(r, {
		item: "рис",
		qty: 500,
		unit: "g",
		step: 50,
		until: "",
		state: "",
		spoil: false,
	});
});

test("pantryRows: просрочено — state expired и кнопка списания", () => {
	const view = { rows: [row({ expires_on: "2026-11-06", expired: true })] };
	const [r] = pantryRows(view, "2026-11-07");
	assert.equal(r.until, "2026-11-06");
	assert.equal(r.state, "expired");
	assert.equal(r.spoil, true);
});

test("pantryRows: скоро — state soon без кнопки списания", () => {
	const view = { rows: [row({ expires_on: "2026-11-08", soon: true })] };
	const [r] = pantryRows(view, "2026-11-07");
	assert.equal(r.state, "soon");
	assert.equal(r.spoil, false);
});

test("pantryRows: будущий день просмотра — expired без кнопки списания", () => {
	const view = { rows: [row({ expires_on: "2026-11-08", expired: true })] };
	const [r] = pantryRows(view, "2026-11-07");
	assert.equal(r.state, "expired");
	assert.equal(r.spoil, false);
});

test("pantryRows: шаг по единице", () => {
	const view = { rows: [row({ unit: "ml" }), row({ unit: "pcs" })] };
	assert.deepEqual(
		pantryRows(view, "2026-11-07").map((r) => r.step),
		[100, 1],
	);
});

test("pantryRows: порядок как в view.rows", () => {
	const view = { rows: [row({ item: "я" }), row({ item: "а" }), row({ item: "м" })] };
	assert.deepEqual(
		pantryRows(view, "2026-11-07").map((r) => r.item),
		["я", "а", "м"],
	);
});

test("parseDelta: мусор — null", () => {
	assert.equal(parseDelta("abc"), null);
	assert.equal(parseDelta(""), null);
	assert.equal(parseDelta("+"), null);
	assert.equal(parseDelta("-"), null);
	assert.equal(parseDelta("+-5"), null);
	assert.equal(parseDelta("12abc"), null);
});

// Строка «записано: …» окна вечернего чек-ина (П10, BACKLOG 95). Данные вымышленные.
import test from "node:test";
import assert from "node:assert/strict";

const { hoursLine } = await import("../../src/ai_coach/web/static/hours-model.js");

test("hoursLine: три вида часов — работа, хобби, отдых", () => {
	assert.equal(hoursLine({ work: 6, hobby: 1.5, rest: 2 }), "записано: работа 6 ч · хобби 1.5 ч · отдых 2 ч");
});

test("hoursLine: один вид — только он", () => {
	assert.equal(hoursLine({ rest: 2 }), "записано: отдых 2 ч");
});

test("hoursLine: порядок — работа, хобби, отдых, как бы ни лежали ключи", () => {
	assert.equal(hoursLine({ hobby: 1, work: 6 }), "записано: работа 6 ч · хобби 1 ч");
});

test("hoursLine: ноль часов — записанное значение, строка есть", () => {
	assert.equal(hoursLine({ work: 0 }), "записано: работа 0 ч");
});

test("hoursLine: пусто, null и undefined — пустая строка", () => {
	assert.equal(hoursLine({}), "");
	assert.equal(hoursLine(null), "");
	assert.equal(hoursLine(undefined), "");
});

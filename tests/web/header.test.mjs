import test from "node:test";
import assert from "node:assert/strict";
import {
	metricsLine,
	syncLine,
	weightLine,
} from "../../src/ai_coach/web/static/header-model.js";

const idle = { running: false, started_at: null, error: null };
const dirty = /null|undefined|NaN/;

test("metricsLine: четыре показателя в порядке Р2", () => {
	const line = metricsLine({ readiness: 72, sleep_h: 7, hrv: 48, rhr: 52 });
	const parts = ["готовность 72", "сон 7 ч", "HRV 48", "пульс 52"];
	const at = parts.map((p) => line.indexOf(p));
	assert.ok(at.every((i) => i >= 0), line);
	assert.deepEqual([...at].sort((a, b) => a - b), at);
});

test("metricsLine: нет данных дня — без null и NaN", () => {
	assert.doesNotMatch(String(metricsLine(null)), dirty);
});

test("metricsLine: пустое поле не печатает null", () => {
	const line = metricsLine({ readiness: null, sleep_h: 7, hrv: 48, rhr: 52 });
	assert.doesNotMatch(line, dirty);
	assert.match(line, /HRV 48/);
});

test("weightLine: вес и единица", () => {
	const line = weightLine({ kg: 82, measured_at: "2026-11-10 07:00:00" });
	assert.match(line, /вес 82 кг/);
});

test("weightLine: записи нет — без null и NaN", () => {
	assert.doesNotMatch(String(weightLine(null)), dirty);
});

test("syncLine: время окончания последнего синка HH:MM", () => {
	const sync = { finished_at: "2026-11-10T17:13:45", status: "ok", running: false };
	assert.match(syncLine(sync, idle), /синк 17:13/);
});

test("syncLine: время из формата с пробелом", () => {
	const sync = { finished_at: "2026-11-10 09:05:00", status: "ok", running: false };
	assert.match(syncLine(sync, idle), /синк 09:05/);
});

test("syncLine: последний синк с ошибкой — слово «ошибка» после времени", () => {
	const sync = { finished_at: "2026-11-10T17:13:45", status: "error", running: false };
	assert.match(syncLine(sync, idle), /синк 17:13 ошибка/);
});

test("syncLine: статус ok, но есть текст ошибки — «ошибка»", () => {
	const sync = {
		finished_at: "2026-11-10T17:13:45",
		status: "ok",
		running: false,
		error: "Токенов Garmin нет. Выполни: coach login",
	};
	assert.match(syncLine(sync, idle), /синк 17:13 ошибка/);
});

test("syncLine: error null — без «ошибка»", () => {
	const sync = { finished_at: "2026-11-10T17:13:45", status: "ok", running: false, error: null };
	assert.doesNotMatch(syncLine(sync, idle), /ошибка/);
});

test("metricsLine: нет строки дня — «показателей нет»", () => {
	assert.equal(metricsLine(null), "показателей нет");
});

test("syncLine: успешный синк без слова «ошибка»", () => {
	const sync = { finished_at: "2026-11-10T17:13:45", status: "ok", running: false };
	assert.doesNotMatch(syncLine(sync, idle), /ошибка/);
});

test("syncLine: идёт синк — «синк идёт…»", () => {
	const sync = { finished_at: "2026-11-10T17:13:45", status: "ok", running: false };
	const running = { running: true, started_at: "2026-11-10T17:20:00", error: null };
	assert.match(syncLine(sync, running), /синк идёт…/);
});

test("metricsLine: дробные часы сна — с точкой", () => {
	const line = metricsLine({ readiness: 72, sleep_h: 7.5, hrv: 48, rhr: 52 });
	assert.match(line, /сон 7\.5 ч/);
});

test("weightLine: дробный вес — с точкой", () => {
	const line = weightLine({ kg: 81.2, measured_at: "2026-11-10 07:00:00" });
	assert.match(line, /вес 81\.2 кг/);
});

test("metricsLine: строка дня, все поля пустые — «показателей нет»", () => {
	const line = metricsLine({ readiness: null, sleep_h: null, hrv: null, rhr: null });
	assert.equal(line, "показателей нет");
});

test("syncLine: синков не было — без null и NaN", () => {
	const sync = { finished_at: null, status: null, running: false };
	assert.doesNotMatch(syncLine(sync, idle), dirty);
});

import test from "node:test";
import assert from "node:assert/strict";
import { icsText, hashText } from "../../player/player.js";

const NOW = new Date(Date.UTC(2026, 9, 9, 12, 0, 0));
const URL_ = "https://example.com/player/#v1.abc";

function payload(extra) {
	return { v: 1, n: "Бег", sp: "run", d: "2026-10-11", b: [{ r: 1, s: [{ k: "work", sec: 600 }] }], ...extra };
}

test("без tm -> DTSTART;VALUE=DATE", () => {
	const text = icsText(payload({}), "v1.abc", URL_, NOW);
	assert.match(text, /\r\nDTSTART;VALUE=DATE:20261011\r\n/);
});

test("без tm нет DTEND", () => {
	assert.doesNotMatch(icsText(payload({}), "v1.abc", URL_, NOW), /DTEND/);
});

test("с tm -> локальное DTSTART", () => {
	const text = icsText(payload({ tm: "18:30" }), "v1.abc", URL_, NOW);
	assert.match(text, /\r\nDTSTART:20261011T183000\r\n/);
});

test("DTEND = старт + totalSeconds", () => {
	const text = icsText(payload({ tm: "18:30" }), "v1.abc", URL_, NOW);
	assert.match(text, /\r\nDTEND:20261011T184000\r\n/);
});

test("DTEND = старт + dur, если задан", () => {
	const text = icsText(payload({ tm: "18:30", dur: 5400 }), "v1.abc", URL_, NOW);
	assert.match(text, /\r\nDTEND:20261011T200000\r\n/);
});

test("DTEND по умолчанию час, если длительность неизвестна", () => {
	const text = icsText({ v: 1, n: "С", d: "2026-10-11", tm: "09:00", b: [] }, "v1.abc", URL_, NOW);
	assert.match(text, /\r\nDTEND:20261011T100000\r\n/);
});

test("DTSTAMP в UTC из now", () => {
	assert.match(icsText(payload({}), "v1.abc", URL_, NOW), /\r\nDTSTAMP:20261009T120000Z\r\n/);
});

test("экранирование запятой в названии", () => {
	assert.match(icsText(payload({ n: "Ноги, спина" }), "v1.abc", URL_, NOW), /SUMMARY:Ноги\\, спина\r\n/);
});

test("экранирование точки с запятой в названии", () => {
	assert.ok(icsText(payload({ n: "А;Б" }), "v1.abc", URL_, NOW).includes("SUMMARY:А" + String.fromCharCode(92) + ";Б\r\n"));
});

test("экранирование перевода строки в названии", () => {
	assert.match(icsText(payload({ n: "А\nБ" }), "v1.abc", URL_, NOW), /SUMMARY:А\\nБ\r\n/);
});

test("экранирование обратного слэша", () => {
	assert.match(icsText(payload({ n: "А\\Б" }), "v1.abc", URL_, NOW), /SUMMARY:А\\\\Б\r\n/);
});

test("URL с фрагментом в URL и DESCRIPTION", () => {
	const text = icsText(payload({}), "v1.abc", URL_, NOW);
	assert.match(text, new RegExp("\\r\\nURL:" + URL_.replace(/[.#/]/g, "\\$&") + "\\r\\n"));
	assert.ok(text.includes("DESCRIPTION:Тренировка: " + URL_));
});

test("строки разделены CRLF, в конце CRLF", () => {
	const text = icsText(payload({}), "v1.abc", URL_, NOW);
	assert.ok(text.endsWith("END:VCALENDAR\r\n"));
	assert.doesNotMatch(text.replace(/\r\n/g, ""), /[\r\n]/);
});

test("начало и конец календаря", () => {
	const text = icsText(payload({}), "v1.abc", URL_, NOW);
	assert.ok(text.startsWith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"));
});

test("UID стабилен для одного фрагмента", () => {
	const a = icsText(payload({}), "v1.abc", URL_, NOW);
	const b = icsText(payload({}), "v1.abc", URL_, new Date(Date.UTC(2027, 0, 1)));
	assert.equal(a.match(/UID:.*/)[0], b.match(/UID:.*/)[0]);
});

test("UID различается для разных фрагментов", () => {
	const a = icsText(payload({}), "v1.abc", URL_, NOW);
	const b = icsText(payload({}), "v1.abd", URL_, NOW);
	assert.notEqual(a.match(/UID:.*/)[0], b.match(/UID:.*/)[0]);
});

test("hashText детерминирован, 8 hex-символов", () => {
	assert.equal(hashText("v1.abc"), hashText("v1.abc"));
	assert.match(hashText("v1.abc"), /^[0-9a-f]{8}$/);
});

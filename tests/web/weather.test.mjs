import test from "node:test";
import assert from "node:assert/strict";

// П7 партия 3: строки погоды на пульте. Имена новые — импорт внутри теста.
const model = () => import("../../src/ai_coach/web/static/weather-model.js");

const CURRENT = { temperature: 3.7, apparent: 0.3, code: 2, wind: 3.09, pressure: 1010 };
const TODAY = { date: "2026-11-22", code: 80, t_max: 5.6, t_min: 1.9, precip_prob: 88 };
const TOMORROW = { date: "2026-11-23", code: 3, t_max: 3.5, t_min: -0.3, precip_prob: 28 };
const DAY = { date: "2026-11-23", code: 3, t_max: 3.5, t_min: -0.3, precip_prob: 28 };
const FETCHED = "2026-11-22T14:10:00";
const fresh = { current: CURRENT, today: TODAY, tomorrow: TOMORROW, fetched_at: FETCHED, stale: false };

test("degrees: 3.7 → +4°", async () => {
	const { degrees } = await model();
	assert.equal(degrees(3.7), "+4°");
});

test("degrees: 0.3 → 0°", async () => {
	const { degrees } = await model();
	assert.equal(degrees(0.3), "0°");
});

test("degrees: −0.3 → 0° без «−0»", async () => {
	const { degrees } = await model();
	assert.equal(degrees(-0.3), "0°");
});

test("degrees: −2.6 → −3° (настоящий минус)", async () => {
	const { degrees } = await model();
	assert.equal(degrees(-2.6), "−3°");
});

test("weatherWord: 0 → ясно", async () => {
	const { weatherWord } = await model();
	assert.equal(weatherWord(0), "ясно");
});

test("weatherWord: 2 → переменная облачность", async () => {
	const { weatherWord } = await model();
	assert.equal(weatherWord(2), "переменная облачность");
});

test("weatherWord: 80 → ливень", async () => {
	const { weatherWord } = await model();
	assert.equal(weatherWord(80), "ливень");
});

test("weatherWord: 3 → пасмурно", async () => {
	const { weatherWord } = await model();
	assert.equal(weatherWord(3), "пасмурно");
});

test("weatherWord: код не из таблицы — пусто", async () => {
	const { weatherWord } = await model();
	assert.ok(!weatherWord(1234));
});

test("weatherLines: сегодня — первая строка «сейчас»", async () => {
	const { weatherLines } = await model();
	assert.equal(
		weatherLines(fresh)[0],
		"сейчас +4° (ощущается 0°) · переменная облачность · ветер 3 м/с",
	);
});

test("weatherLines: сегодня — вторая строка «сегодня · завтра»", async () => {
	const { weatherLines } = await model();
	assert.equal(
		weatherLines(fresh)[1],
		"сегодня +2…+6°, ливень, осадки 88% · завтра 0…+4°, пасмурно, осадки 28%",
	);
});

test("weatherLines: сегодня — ровно две строки", async () => {
	const { weatherLines } = await model();
	assert.equal(weatherLines(fresh).length, 2);
});

test("weatherLines: «ощущается» равно температуре после округления — скобок нет", async () => {
	const { weatherLines } = await model();
	const view = { ...fresh, current: { ...CURRENT, apparent: 3.9 } };
	assert.equal(weatherLines(view)[0], "сейчас +4° · переменная облачность · ветер 3 м/с");
});

test("weatherLines: код не из таблицы — часть строки пропущена", async () => {
	const { weatherLines } = await model();
	const view = { ...fresh, current: { ...CURRENT, code: 1234 } };
	assert.equal(weatherLines(view)[0], "сейчас +4° (ощущается 0°) · ветер 3 м/с");
});

test("weatherLines: будущий день — одна строка прогноза", async () => {
	const { weatherLines } = await model();
	const view = { day: DAY, fetched_at: FETCHED, stale: false };
	assert.deepEqual(weatherLines(view), ["прогноз: 0…+4°, пасмурно, осадки 28%"]);
});

test("weatherLines: missing range — строк нет", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines({ missing: "range" }), []);
});

test("weatherLines: до ответа (null) — «погода: …»", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines(null), ["погода: …"]);
});

test("weatherLines: missing silent — «погода: нет связи»", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines({ missing: "silent" }), ["погода: нет связи"]);
});

test("weatherLines: stale, сегодня — первая строка начинается с «погода на 14:10: »", async () => {
	const { weatherLines } = await model();
	const lines = weatherLines({ ...fresh, stale: true });
	assert.ok(lines[0].startsWith("погода на 14:10: "), lines[0]);
});

test("weatherLines: stale, будущий день — «погода на 14:10: прогноз …» (Р47 = 1)", async () => {
	const { weatherLines } = await model();
	const view = { day: DAY, fetched_at: FETCHED, stale: true };
	assert.deepEqual(weatherLines(view), ["погода на 14:10: прогноз 0…+4°, пасмурно, осадки 28%"]);
});

test("weatherLines: missing place, denied → нет доступа к геолокации", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines({ missing: "place", why: "denied" }), [
		"погода: нет доступа к геолокации",
	]);
});

test("weatherLines: missing place, off → нет доступа к геолокации", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines({ missing: "place", why: "off" }), [
		"погода: нет доступа к геолокации",
	]);
});

test("weatherLines: missing place, timeout → место не определено", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines({ missing: "place", why: "timeout" }), [
		"погода: место не определено",
	]);
});

test("weatherLines: missing place, why не из четырёх → место не определено (Р50 = 1)", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines({ missing: "place", why: "что-то новое" }), [
		"погода: место не определено",
	]);
});

test("weatherLines: missing place без why → место не определено (Р50 = 1)", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines({ missing: "place" }), ["погода: место не определено"]);
});

test("weatherLines: у дня без precip_prob нет части «осадки» (Р53 = 1)", async () => {
	const { weatherLines } = await model();
	const view = { ...fresh, today: { ...TODAY, precip_prob: null } };
	assert.deepEqual(weatherLines(view)[1], "сегодня +2…+6°, ливень · завтра 0…+4°, пасмурно, осадки 28%");
});

test("weatherLines: будущий день без precip_prob — без «осадки»", async () => {
	const { weatherLines } = await model();
	const view = { day: { ...DAY, precip_prob: null }, fetched_at: FETCHED, stale: false };
	assert.deepEqual(weatherLines(view), ["прогноз: 0…+4°, пасмурно"]);
});

test("weatherLines: missing place, unavailable → место не определено", async () => {
	const { weatherLines } = await model();
	assert.deepEqual(weatherLines({ missing: "place", why: "unavailable" }), [
		"погода: место не определено",
	]);
});

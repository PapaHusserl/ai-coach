import test from "node:test";
import assert from "node:assert/strict";
import {
	barLabel,
	barPercent,
	dayRows,
	formatClock,
	formatDate,
	isCurrent,
	shiftDay,
} from "../../src/ai_coach/web/static/pult.js";

test("formatClock берёт HH:MM", () => {
	assert.equal(formatClock("2026-11-07T09:05:00"), "09:05");
});

test("formatDate 2026-11-07", () => {
	assert.equal(formatDate("2026-11-07"), "сб, 7 ноября");
});

test("formatDate воскресенье и декабрь", () => {
	assert.equal(formatDate("2026-12-27"), "вс, 27 декабря");
});

test("barPercent середина", () => {
	assert.equal(barPercent(90, 150), 38);
});

test("barPercent пустой день — 0", () => {
	assert.equal(barPercent(0, 0), 0);
});

test("barPercent всё прошло — 100", () => {
	assert.equal(barPercent(240, 0), 100);
});

test("barPercent ничего не прошло — 0", () => {
	assert.equal(barPercent(0, 240), 0);
});

test("barPercent не выходит за 0..100", () => {
	assert.equal(barPercent(500, -100), 100);
	assert.equal(barPercent(-100, 500), 0);
});

test("shiftDay вперёд через границу месяца", () => {
	assert.equal(shiftDay("2026-11-30", 1), "2026-12-01");
});

test("shiftDay назад через границу года", () => {
	assert.equal(shiftDay("2027-01-01", -1), "2026-12-31");
});

test("isCurrent сверяет source и id", () => {
	const current = [{ source: "meeting", id: 5 }];
	assert.equal(isCurrent(current, "meeting", 5), true);
	assert.equal(isCurrent(current, "item", 5), false);
	assert.equal(isCurrent(current, "meeting", 6), false);
});

const view = {
	items: [
		{ id: 1, start_at: "2026-11-07T12:00:00", end_at: "2026-11-07T13:00:00", all_day: false },
		{ id: 2, start_at: "2026-11-07T10:30:00", end_at: "2026-11-07T11:30:00", all_day: false },
	],
	meetings: [
		{ id: 7, start_at: "2026-11-07T10:00:00", end_at: "2026-11-07T11:00:00", all_day: false },
		{ id: 8, start_at: "2026-11-07T00:00:00", end_at: "2026-11-08T00:00:00", all_day: true },
	],
	current: [
		{ source: "meeting", id: 7 },
		{ source: "item", id: 2 },
	],
};

test("dayRows: все элементы current подсвечены, прочие нет", () => {
	const rows = dayRows(view);
	const flags = Object.fromEntries(rows.map((r) => [`${r.source}${r.id}`, r.current]));
	assert.deepEqual(flags, { meeting7: true, item2: true, item1: false, meeting8: false });
});

test("dayRows: встречи серые, пункты нет", () => {
	const rows = dayRows(view);
	assert.deepEqual(
		rows.map((r) => [r.source, r.muted]),
		[["meeting", true], ["meeting", true], ["item", false], ["item", false]],
	);
});

test("dayRows: весь день сверху, остальные по началу", () => {
	assert.deepEqual(
		dayRows(view).map((r) => r.id),
		[8, 7, 2, 1],
	);
});

test("dayRows: пустой день", () => {
	assert.deepEqual(dayRows({ items: [], meetings: [], current: [] }), []);
});

test("barLabel минуты и часы", () => {
	assert.equal(barLabel(90, 120), "прошло 1 ч 30 мин / осталось 2 ч 0 мин");
	assert.equal(barLabel(0, 30), "прошло 0 мин / осталось 30 мин");
});

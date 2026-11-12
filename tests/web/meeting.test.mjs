import test from "node:test";
import assert from "node:assert/strict";

const MODEL = "../../src/ai_coach/web/static/meeting-model.js";

const view = (start, end, extra) => ({ start_at: start, end_at: end, all_day: false, ...extra });

test("newTimes: дата +1 — оба конца на новой дате, время как в полях", async () => {
	const { newTimes } = await import(MODEL);
	const v = view("2026-11-12T10:00:00", "2026-11-12T11:00:00");
	assert.deepEqual(newTimes(v, "2026-11-13", "10:00", "11:00"), {
		start_at: "2026-11-13T10:00:00",
		end_at: "2026-11-13T11:00:00",
	});
});

test("newTimes: время берётся из полей, не из события", async () => {
	const { newTimes } = await import(MODEL);
	const v = view("2026-11-12T10:00:00", "2026-11-12T11:00:00");
	assert.deepEqual(newTimes(v, "2026-11-12", "09:15", "09:45"), {
		start_at: "2026-11-12T09:15:00",
		end_at: "2026-11-12T09:45:00",
	});
});

test("newTimes: «до 00:00» при span 0 — конец на следующие сутки", async () => {
	const { newTimes } = await import(MODEL);
	const v = view("2026-11-12T23:00:00", "2026-11-12T23:30:00");
	assert.deepEqual(newTimes(v, "2026-11-12", "23:00", "00:00"), {
		start_at: "2026-11-12T23:00:00",
		end_at: "2026-11-13T00:00:00",
	});
});

test("newTimes: событие через полночь (span 1) — конец на date + 1", async () => {
	const { newTimes } = await import(MODEL);
	const v = view("2026-11-12T23:00:00", "2026-11-13T01:00:00");
	assert.deepEqual(newTimes(v, "2026-11-20", "23:00", "01:00"), {
		start_at: "2026-11-20T23:00:00",
		end_at: "2026-11-21T01:00:00",
	});
});

test("newTimes: all_day, дата +1 — оба конца на сутки вперёд", async () => {
	const { newTimes } = await import(MODEL);
	const v = view("2026-11-12T00:00:00", "2026-11-13T00:00:00", { all_day: true });
	assert.deepEqual(newTimes(v, "2026-11-13", "", ""), {
		start_at: "2026-11-13T00:00:00",
		end_at: "2026-11-14T00:00:00",
	});
});

test("newTimes: all_day, дата 14-е — оба конца +2 суток, время не трогается", async () => {
	const { newTimes } = await import(MODEL);
	const v = view("2026-11-12T00:00:00", "2026-11-13T00:00:00", { all_day: true });
	assert.deepEqual(newTimes(v, "2026-11-14", "10:00", "11:00"), {
		start_at: "2026-11-14T00:00:00",
		end_at: "2026-11-15T00:00:00",
	});
});

test("dayDiff: через смену месяца", async () => {
	const { dayDiff } = await import(MODEL);
	assert.equal(dayDiff("2026-10-30T10:00:00", "2026-11-02T08:00:00"), 3);
});

test("dayDiff: назад — отрицательное, тот же день — 0", async () => {
	const { dayDiff } = await import(MODEL);
	assert.equal(dayDiff("2026-11-02T00:00:00", "2026-10-31T23:00:00"), -2);
	assert.equal(dayDiff("2026-11-02T00:00:00", "2026-11-02T23:59:00"), 0);
});

test("shiftIso: −1 сутки через границу месяца", async () => {
	const { shiftIso } = await import(MODEL);
	assert.equal(shiftIso("2026-11-01T10:30:00", -1), "2026-10-31T10:30:00");
});

test("shiftIso: +2 суток, время сохраняется", async () => {
	const { shiftIso } = await import(MODEL);
	assert.equal(shiftIso("2026-11-12T00:00:00", 2), "2026-11-14T00:00:00");
});

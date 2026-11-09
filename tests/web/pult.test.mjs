import test from "node:test";
import assert from "node:assert/strict";
import {
	barLabel,
	barPercent,
	dayRows,
	formatClock,
	formatDate,
	hasWindow,
	isCurrent,
	itemProgress,
	nextRow,
	openedId,
	rowStatus,
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
	assert.equal(barLabel(60, 0), "прошло 1 ч 0 мин / осталось 0 мин");
});

const NOW = "2026-11-07T12:00:00";
const noMarks = { ratings: [], done: null, food: [] };
const itemRow = (extra) => ({
	source: "item",
	kind: "task",
	start_at: "2026-11-07T10:00:00",
	end_at: "2026-11-07T11:00:00",
	all_day: false,
	current: false,
	due: false,
	marks: noMarks,
	...extra,
});

test("rowStatus: текущий — «идёт»", () => {
	assert.deepEqual(rowStatus(itemRow({ current: true }), NOW, false), { text: "идёт", tone: "live" });
});

test("rowStatus: текущая встреча тоже «идёт»", () => {
	assert.deepEqual(rowStatus({ source: "meeting", current: true }, NOW, false), { text: "идёт", tone: "live" });
});

test("rowStatus: прошедший со сводкой отметок", () => {
	const marks = { ratings: [{ focus: 4, fatigue: 2, effort: 3 }], done: null, food: [] };
	assert.deepEqual(rowStatus(itemRow({ marks }), NOW, false), { text: "4/2/3", tone: "good" });
});

test("rowStatus: прошедший due — «не заполнено»", () => {
	assert.deepEqual(rowStatus(itemRow({ due: true }), NOW, false), { text: "не заполнено", tone: "bad" });
});

test("rowStatus: прошедший без отметок — тип пункта", () => {
	assert.deepEqual(rowStatus(itemRow({ kind: "practice" }), NOW, false), { text: "практика", tone: "" });
});

test("rowStatus: ближайший будущий — «через N мин»", () => {
	const row = itemRow({ start_at: "2026-11-07T12:25:00", end_at: "2026-11-07T13:00:00" });
	assert.deepEqual(rowStatus(row, NOW, true), { text: "через 25 мин", tone: "" });
});

test("rowStatus: ближайший будущий от часа — «через 1 ч 5 мин»", () => {
	const row = itemRow({ start_at: "2026-11-07T13:05:00", end_at: "2026-11-07T14:00:00" });
	assert.deepEqual(rowStatus(row, NOW, true), { text: "через 1 ч 5 мин", tone: "" });
});

test("rowStatus: будущий не ближайший — тип пункта", () => {
	const row = itemRow({ start_at: "2026-11-07T15:00:00", end_at: "2026-11-07T16:00:00", kind: "rest" });
	assert.deepEqual(rowStatus(row, NOW, false), { text: "отдых", tone: "" });
});

test("rowStatus: фокус подписан «фокус» (Р10)", () => {
	const row = itemRow({ start_at: "2026-11-07T15:00:00", end_at: "2026-11-07T16:00:00", kind: "focus" });
	assert.equal(rowStatus(row, NOW, false).text, "фокус");
});

test("rowStatus: не текущая встреча — пусто", () => {
	assert.deepEqual(rowStatus({ source: "meeting", current: false }, NOW, true), { text: "", tone: "" });
});

test("rowStatus: пункт без окна — пусто", () => {
	assert.deepEqual(rowStatus(itemRow({ kind: "other" }), NOW, false), { text: "", tone: "" });
});

const mealMarks = (food) => ({ ratings: [], feel: [], slips: [], done: null, food });
const eaten = [{ id: 1, text: "омлет", kcal: null, logged_at: "2026-11-07 10:30:00" }];

test("rowStatus: прошедшая еда с записью — «съел», good", () => {
	const row = itemRow({ kind: "meal", meal: { remaining: null, food: eaten }, marks: mealMarks(eaten) });
	assert.deepEqual(rowStatus(row, NOW, false), { text: "съел", tone: "good" });
});

test("rowStatus: прошедшая еда без записи и due — «не заполнено»", () => {
	const row = itemRow({ kind: "meal", meal: { remaining: null, food: [] }, marks: mealMarks([]), due: true });
	assert.deepEqual(rowStatus(row, NOW, false), { text: "не заполнено", tone: "bad" });
});

test("rowStatus: будущая еда не ближайшая — подпись есть, не «съел»", () => {
	const row = itemRow({
		kind: "meal",
		meal: { remaining: null, food: [] },
		marks: mealMarks([]),
		start_at: "2026-11-07T13:00:00",
		end_at: "2026-11-07T14:00:00",
	});
	const status = rowStatus(row, NOW, false);
	assert.equal(status.tone, "");
	assert.notEqual(status.text, "");
	assert.notEqual(status.text, "съел");
});

test("hasWindow: еда с ключом meal — есть окно", () => {
	assert.equal(hasWindow(itemRow({ kind: "meal", meal: { remaining: null, food: [] } })), true);
});

test("hasWindow: еда без ключа meal («Готовка») — окна нет", () => {
	assert.equal(hasWindow(itemRow({ kind: "meal" })), false);
});

test("hasWindow: у остальных видов ключ meal не нужен, встреча — нет", () => {
	assert.equal(hasWindow(itemRow({ kind: "task" })), true);
	assert.equal(hasWindow({ source: "meeting", kind: "meal", meal: {} }), false);
});

test("rowStatus: «Готовка» без окна — пусто", () => {
	assert.deepEqual(rowStatus(itemRow({ kind: "meal" }), NOW, false), { text: "", tone: "" });
});

test("openedId: «Готовка» не раскрывается, ни сама, ни по клику", () => {
	const cooking = itemRow({ id: 1, kind: "meal", current: true });
	const breakfast = itemRow({ id: 2, kind: "meal", meal: { remaining: null, food: [] }, current: true });
	assert.equal(openedId(null, [cooking, breakfast]), 2);
	assert.equal(openedId(1, [cooking]), null);
});

const cur = (extra) =>
	itemRow({ start_at: "2026-11-07T11:00:00", end_at: "2026-11-07T13:00:00", current: true, ...extra });

test("itemProgress: начало — 0 %", () => {
	assert.deepEqual(itemProgress(cur(), "2026-11-07T11:00:00"), {
		percent: 0,
		elapsedMin: 0,
		leftMin: 120,
		until: "13:00",
	});
});

test("itemProgress: середина — 50 %", () => {
	assert.deepEqual(itemProgress(cur(), "2026-11-07T12:00:00"), {
		percent: 50,
		elapsedMin: 60,
		leftMin: 60,
		until: "13:00",
	});
});

test("itemProgress: конец и позже — не больше 100 %", () => {
	const late = itemProgress(cur(), "2026-11-07T14:00:00");
	assert.deepEqual([late.percent, late.elapsedMin, late.leftMin], [100, 120, 0]);
});

test("itemProgress: до начала — 0 %", () => {
	assert.equal(itemProgress(cur(), "2026-11-07T10:00:00").percent, 0);
});

test("itemProgress: на весь день — нет бара", () => {
	assert.equal(itemProgress(cur({ all_day: true }), NOW), null);
});

test("itemProgress: считается для каждого пункта отдельно, пересечение не мешает", () => {
	const other = cur({ start_at: "2026-11-07T11:30:00", end_at: "2026-11-07T12:30:00" });
	assert.deepEqual(
		[itemProgress(cur(), NOW).percent, itemProgress(other, NOW).percent],
		[50, 50],
	);
});

const todayView = { date: "2026-11-07", now: NOW };
const later = (id, extra) =>
	itemRow({ id, start_at: "2026-11-07T14:00:00", end_at: "2026-11-07T15:00:00", ...extra });

test("nextRow: сегодня — первый будущий пункт с окном, встреча и весь день пропущены", () => {
	const meeting = { source: "meeting", start_at: "2026-11-07T12:30:00", end_at: "2026-11-07T13:00:00" };
	const allDay = later(1, { all_day: true });
	const noWindow = later(2, { kind: "other", start_at: "2026-11-07T13:00:00" });
	const first = later(3);
	const rows = [itemRow({ id: 0 }), meeting, allDay, noWindow, first, later(4)];
	assert.equal(nextRow(rows, todayView), first);
});

test("openedId: идущий раскрыт сам, клик выбирает, false сворачивает", () => {
	const running = itemRow({ id: 1, current: true });
	const other = later(2);
	const meeting = { source: "meeting", id: 3, current: true };
	const rows = [meeting, running, other];
	assert.equal(openedId(null, rows), 1);
	assert.equal(openedId(2, rows), 2);
	assert.equal(openedId(false, rows), null);
	assert.equal(openedId(99, rows), 1);
	assert.equal(openedId(null, [other]), null);
});

test("openedId: два идущих — раскрыт первый по списку (Р18), второй выбирается кликом", () => {
	const first = itemRow({ id: 1, current: true });
	const second = itemRow({ id: 2, current: true });
	assert.equal(openedId(null, [first, second]), 1);
	assert.equal(openedId(2, [first, second]), 2);
});

test("openedId: id встречи или пункта без окна не раскрывается", () => {
	const running = itemRow({ id: 1, current: true });
	const meeting = { source: "meeting", id: 5, current: false };
	const noWindow = itemRow({ id: 6, kind: "other" });
	assert.equal(openedId(5, [meeting, running]), 1);
	assert.equal(openedId(6, [noWindow, running]), 1);
});

test("nextRow: нет будущих пунктов с окном — undefined", () => {
	assert.equal(nextRow([itemRow({ id: 0 })], todayView), undefined);
});

test("nextRow: чужой день — undefined", () => {
	const view = { date: "2026-11-08", now: NOW };
	assert.equal(nextRow([later(1)], view), undefined);
});

// Партия 4: тренировка.
const trainMarks = { ratings: [], feel: [], slips: [], done: null, food: [] };
const plan = { name: "Бег", sport: "run", duration_min: 45, steps: [] };
const factOf = (kind) => ({ kind, rows: [], zones: null });
const trainRow = (training, extra) =>
	itemRow({ kind: "training", training, marks: trainMarks, ...extra });

test("hasWindow: тренировка с training — окно есть", () => {
	assert.equal(hasWindow(trainRow({ plan, fact: null })), true);
});

test("hasWindow: тренировка без ключа training (Р15 = 1) — окно есть", () => {
	assert.equal(hasWindow(itemRow({ kind: "training", marks: trainMarks })), true);
});

test("rowStatus: прошедшая тренировка с фактом done и без отметки — «✓ по плану», good", () => {
	const row = trainRow({ plan, fact: factOf("done") });
	assert.deepEqual(rowStatus(row, NOW, false), { text: "✓ по плану", tone: "good" });
});

test("rowStatus: прошедшая тренировка due — «не заполнено»", () => {
	const row = trainRow({ plan, fact: factOf("skipped") }, { due: true });
	assert.deepEqual(rowStatus(row, NOW, false), { text: "не заполнено", tone: "bad" });
});

test("rowStatus: прошедшая тренировка с отметкой «сделал» без факта — «сделал»", () => {
	const marks = { ...trainMarks, done: { done: 1, logged_at: "2026-11-07 11:00:00" } };
	const row = trainRow({ plan, fact: null }, { marks });
	assert.deepEqual(rowStatus(row, NOW, false), { text: "сделал", tone: "good" });
});

test("rowStatus: будущая тренировка не ближайшая — «тренировка»", () => {
	const row = trainRow(
		{ plan, fact: null },
		{ start_at: "2026-11-07T13:00:00", end_at: "2026-11-07T14:00:00" },
	);
	assert.deepEqual(rowStatus(row, NOW, false), { text: "тренировка", tone: "" });
});

test("rowStatus: прошедшая тренировка без факта и отметок, не due — «тренировка»", () => {
	const row = trainRow({ plan, fact: null });
	assert.deepEqual(rowStatus(row, NOW, false), { text: "тренировка", tone: "" });
});

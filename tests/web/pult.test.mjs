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

test("hasWindow: чек-ин «без анкеты» — окно есть (Сделал / Пропустил)", () => {
	assert.equal(hasWindow(itemRow({ kind: "checkin", survey: "none" })), true);
});

test("hasWindow: у остальных видов ключ meal не нужен", () => {
	assert.equal(hasWindow(itemRow({ kind: "task" })), true);
});

test("hasWindow: у встречи окно есть (Р7 = 1)", () => {
	assert.equal(hasWindow({ source: "meeting", editable: true, recurring: false }), true);
});

test("hasWindow: у встречи окно есть и без editable (просмотр, Р9 = 1)", () => {
	assert.equal(hasWindow({ source: "meeting", editable: false }), true);
});

test("noteText: заметка пункта тренера возвращается строкой", async () => {
	const { noteText } = await import("../../src/ai_coach/web/static/pult.js");
	assert.equal(noteText({ source: "item", note: "uv run coach pvt" }), "uv run coach pvt");
});

test("noteText: note null — пустая строка", async () => {
	const { noteText } = await import("../../src/ai_coach/web/static/pult.js");
	assert.equal(noteText({ source: "item", note: null }), "");
});

test("noteText: нет ключа note — пустая строка", async () => {
	const { noteText } = await import("../../src/ai_coach/web/static/pult.js");
	assert.equal(noteText({ source: "item" }), "");
});

test("noteText: пустая заметка — пустая строка", async () => {
	const { noteText } = await import("../../src/ai_coach/web/static/pult.js");
	assert.equal(noteText({ source: "item", note: "" }), "");
});

test("noteText: у встречи заметки нет, описание — в её окне", async () => {
	const { noteText } = await import("../../src/ai_coach/web/static/pult.js");
	assert.equal(noteText({ source: "meeting", note: "x" }), "");
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

test("nextRow: будущая встреча с окном перед будущим пунктом — берётся пункт", () => {
	const meeting = {
		source: "meeting",
		editable: true,
		start_at: "2026-11-07T12:30:00",
		end_at: "2026-11-07T13:00:00",
		all_day: false,
	};
	const item = later(1);
	assert.equal(nextRow([meeting, item], todayView), item);
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

// Партия 5: вкладка «Тренировки». Имена новые — импорт внутри теста.
const pultModel = () => import("../../src/ai_coach/web/static/pult.js");
const planned = (status, id = 1, name = "Бег") => ({ id, name, sport: "run", status });
// Факт плана связан с ним по planned_id; активность вне плана ключа не имеет.
const fact = (kind, plannedId = 1) => ({
	kind,
	name: "Бег",
	activity_id: kind === "skipped" ? null : 5,
	...(kind === "extra" ? {} : { planned_id: plannedId }),
});
const WEEK_DATES = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"];
const weekOf = (byDate) => ({
	days: WEEK_DATES.map((date) => ({ date, planned: [], fact: [], ...byDate[date] })),
});
const pillTexts = (rows, index) => rows[index].items.map((item) => item.pill.text);
const titles = (rows, index) => rows[index].items.map((item) => item.title);

test("weekRows: семь строк по датам недели", async () => {
	const { weekRows } = await pultModel();
	assert.deepEqual(weekRows(weekOf({})).map((r) => r.date), WEEK_DATES);
});

test("weekRows: сегодня помечен только сегодняшний день", async () => {
	const { weekRows } = await pultModel();
	const rows = weekRows(weekOf({}), "2026-11-13");
	assert.deepEqual(rows.map((r) => r.today), [false, false, false, false, true, false, false]);
});

test("weekRows: день без плана и факта — «отдых»", async () => {
	const { weekRows } = await pultModel();
	assert.deepEqual(pillTexts(weekRows(weekOf({})), 0), ["отдых"]);
});

test("weekRows: отправленная на часы — «на часах»", async () => {
	const { weekRows } = await pultModel();
	const rows = weekRows(weekOf({ "2026-11-12": { planned: [planned("pushed")] } }));
	assert.deepEqual(pillTexts(rows, 3), ["на часах"]);
});

test("weekRows: черновик и утверждённая — «в плане»", async () => {
	const { weekRows } = await pultModel();
	const week = weekOf({
		"2026-11-12": { planned: [planned("draft")] },
		"2026-11-13": { planned: [planned("approved")] },
	});
	const rows = weekRows(week);
	assert.deepEqual(pillTexts(rows, 3), ["в плане"]);
	assert.deepEqual(pillTexts(rows, 4), ["в плане"]);
});

test("weekRows: отменённая тренировка не считается — «отдых»", async () => {
	const { weekRows } = await pultModel();
	const rows = weekRows(weekOf({ "2026-11-12": { planned: [planned("cancelled")] } }));
	assert.deepEqual(pillTexts(rows, 3), ["отдых"]);
});

test("weekRows: факт done заменяет плашку плана — «сделано»", async () => {
	const { weekRows } = await pultModel();
	const day = { planned: [planned("pushed")], fact: [fact("done")] };
	assert.deepEqual(pillTexts(weekRows(weekOf({ "2026-11-10": day })), 1), ["сделано"]);
});

test("weekRows: факт different — «выполнено иначе», тон warn", async () => {
	const { weekRows } = await pultModel();
	const day = { planned: [planned("pushed")], fact: [fact("different")] };
	const rows = weekRows(weekOf({ "2026-11-10": day }));
	assert.deepEqual(rows[1].items[0].pill, { text: "выполнено иначе", tone: "warn" });
});

test("weekRows: факт done — плашка «сделано», тон good", async () => {
	const { weekRows } = await pultModel();
	const day = { planned: [planned("pushed")], fact: [fact("done")] };
	const rows = weekRows(weekOf({ "2026-11-10": day }));
	assert.deepEqual(rows[1].items[0].pill, { text: "сделано", tone: "good" });
});

test("weekRows: подпись дня — «Пн 9»", async () => {
	const { weekRows } = await pultModel();
	assert.equal(weekRows(weekOf({}))[0].label, "Пн 9");
});

test("weekRows: факт skipped — «пропущено»", async () => {
	const { weekRows } = await pultModel();
	const day = { planned: [planned("pushed")], fact: [fact("skipped")] };
	assert.deepEqual(pillTexts(weekRows(weekOf({ "2026-11-10": day })), 1), ["пропущено"]);
});

test("weekRows: активность без плана — «вне плана»", async () => {
	const { weekRows } = await pultModel();
	const day = { fact: [fact("extra")] };
	assert.deepEqual(pillTexts(weekRows(weekOf({ "2026-11-14": day })), 5), ["вне плана"]);
});

test("weekRows: план без факта и вне плана рядом — обе плашки", async () => {
	const { weekRows } = await pultModel();
	const day = { planned: [planned("pushed")], fact: [fact("extra")] };
	assert.deepEqual(pillTexts(weekRows(weekOf({ "2026-11-10": day })), 1), ["на часах", "вне плана"]);
});

test("weekRows: у каждой тренировки своя строка — имя и плашка; вне плана тоже строкой", async () => {
	const { weekRows } = await pultModel();
	const day = {
		planned: [planned("pushed", 1, "Бег"), planned("pushed", 2, "Растяжка")],
		fact: [{ ...fact("extra"), name: "Прогулка" }],
	};
	const rows = weekRows(weekOf({ "2026-11-10": day }));
	assert.deepEqual(titles(rows, 1), ["Бег", "Растяжка", "Прогулка"]);
	assert.deepEqual(pillTexts(rows, 1), ["на часах", "на часах", "вне плана"]);
});

test("weekRows: пустой день — строка «—» с плашкой «отдых»", async () => {
	const { weekRows } = await pultModel();
	const rows = weekRows(weekOf({}));
	assert.deepEqual(titles(rows, 0), ["—"]);
	assert.deepEqual(pillTexts(rows, 0), ["отдых"]);
});

test("weekRows: [черновик, отправленная], факт у второй — «в плане», «сделано»", async () => {
	const { weekRows } = await pultModel();
	const day = {
		planned: [planned("draft", 1, "А"), planned("pushed", 2, "Б")],
		fact: [fact("done", 2)],
	};
	const rows = weekRows(weekOf({ "2026-11-10": day }));
	assert.deepEqual(titles(rows, 1), ["А", "Б"]);
	assert.deepEqual(pillTexts(rows, 1), ["в плане", "сделано"]);
});

test("weekRows: два плана, факты в другом порядке — плашка по planned_id", async () => {
	const { weekRows } = await pultModel();
	const day = {
		planned: [planned("pushed", 1, "А"), planned("pushed", 2, "Б")],
		fact: [fact("done", 2), fact("skipped", 1)],
	};
	const rows = weekRows(weekOf({ "2026-11-10": day }));
	assert.deepEqual(pillTexts(rows, 1), ["пропущено", "сделано"]);
});

test("weekTitle: внутри месяца — «Неделя 9–15 ноября»", async () => {
	const { weekTitle } = await pultModel();
	assert.equal(weekTitle(weekOf({})), "Неделя 9–15 ноября");
});

test("weekTitle: через границу месяца — «Неделя 26 октября – 1 ноября»", async () => {
	const { weekTitle } = await pultModel();
	const dates = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"];
	assert.equal(weekTitle({ days: dates.map((date) => ({ date })) }), "Неделя 26 октября – 1 ноября");
});

// Партия 5 П4: chartPoints переехала в chart.js (общий с «Состоянием»). Импорт внутри теста.
const chartModule = () => import("../../src/ai_coach/web/static/chart.js");
const BOX = { x0: 10, x1: 110, y0: 0, y1: 100, min: 0, max: 16 };

test("chartPoints: первая точка на x0, последняя на x1, значения по высоте", async () => {
	const { chartPoints } = await chartModule();
	assert.deepEqual(chartPoints([0, 8, 16], BOX), [
		[10, 100],
		[60, 50],
		[110, 0],
	]);
});

test("chartPoints: верх рамки y0 не ноль — отсчёт от y1 вверх до y0", async () => {
	const { chartPoints } = await chartModule();
	assert.deepEqual(chartPoints([16, 0], { ...BOX, y0: 10 }), [
		[10, 10],
		[110, 100],
	]);
});

test("chartPoints: равные шаги по x для четырёх точек", async () => {
	const { chartPoints } = await chartModule();
	const xs = chartPoints([1, 2, 3, 4], BOX).map((p) => p[0]);
	assert.deepEqual(xs, [10, 10 + 100 / 3, 10 + 200 / 3, 110]);
});

test("chartPoints: пустой ряд — пусто", async () => {
	const { chartPoints } = await chartModule();
	assert.deepEqual(chartPoints([], BOX), []);
});

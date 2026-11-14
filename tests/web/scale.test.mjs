import test from "node:test";
import assert from "node:assert/strict";

const MODEL = "../../src/ai_coach/web/static/scale-model.js";
const DAY = "2026-11-09";

const at = (hhmm) => `${DAY}T${hhmm}:00`;
const row = (start, end, extra) => ({ id: 1, start_at: at(start), end_at: at(end), all_day: false, repeat: null, ...extra });
const view = (items, meetings = []) => ({ date: DAY, items, meetings });

test("frameOf: рамка бара ± 1 ч", async () => {
	const { frameOf } = await import(MODEL);
	const frame = frameOf(view([row("09:00", "10:00"), row("12:00", "13:00")]));
	assert.deepEqual([frame.start, frame.end], [8 * 60, 14 * 60]);
});

test("frameOf: встреча раньше и позже пунктов растягивает рамку", async () => {
	const { frameOf } = await import(MODEL);
	const frame = frameOf(view([row("09:00", "10:00")], [row("08:00", "08:30"), row("15:00", "16:00")]));
	assert.deepEqual([frame.start, frame.end], [7 * 60, 17 * 60]);
});

test("frameOf: пункт на весь день рамку не двигает", async () => {
	const { frameOf } = await import(MODEL);
	const allDay = row("00:00", "23:59", { all_day: true });
	const frame = frameOf(view([row("09:00", "10:00"), allDay]));
	assert.deepEqual([frame.start, frame.end], [8 * 60, 11 * 60]);
});

test("frameOf: рамка не выходит за сутки", async () => {
	const { frameOf } = await import(MODEL);
	const frame = frameOf(view([row("00:30", "23:30")]));
	assert.deepEqual([frame.start, frame.end], [0, 24 * 60]);
});

test("minuteAt: начало, середина и конец полосы", async () => {
	const { minuteAt } = await import(MODEL);
	const frame = { start: 480, end: 840 };
	assert.equal(minuteAt(0, 360, frame), 480);
	assert.equal(minuteAt(180, 360, frame), 660);
	assert.equal(minuteAt(360, 360, frame), 840);
});

test("minuteAt: за краем полосы — край рамки", async () => {
	const { minuteAt } = await import(MODEL);
	const frame = { start: 480, end: 840 };
	assert.equal(minuteAt(-20, 360, frame), 480);
	assert.equal(minuteAt(400, 360, frame), 840);
});

test("snap: к ближайшим 5 минутам", async () => {
	const { snap } = await import(MODEL);
	assert.equal(snap(542, 5), 540);
	assert.equal(snap(543, 5), 545);
	assert.equal(snap(545, 5), 545);
});

test("blockBox: left и width в процентах рамки", async () => {
	const { blockBox } = await import(MODEL);
	const frame = { start: 480, end: 840 }; // 08:00–14:00, 360 мин
	const box = blockBox(row("09:00", "10:30"), frame);
	assert.equal(box.left, 100 * 60 / 360);
	assert.equal(box.width, 100 * 90 / 360);
});

test("dragOutcome move: сдвиг, длительность та же", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("move", row("09:00", "10:00"), 30);
	assert.deepEqual(out, { start_at: at("09:30"), end_at: at("10:30") });
});

test("dragOutcome move: сдвиг назад", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("move", row("09:00", "10:00"), -45);
	assert.deepEqual(out, { start_at: at("08:15"), end_at: at("09:15") });
});

test("dragOutcome resize: начало на месте, конец сдвинут", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("resize", row("09:00", "10:00"), 25);
	assert.deepEqual(out, { start_at: at("09:00"), end_at: at("10:25") });
});

test("dragOutcome resize: длительность не меньше 5 минут", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("resize", row("09:00", "10:00"), -120);
	assert.deepEqual(out, { start_at: at("09:00"), end_at: at("09:05") });
});

test("newSpan: 30 минут от снапа клика", async () => {
	const { newSpan } = await import(MODEL);
	const span = newSpan(542, { start: 480, end: 840 });
	assert.deepEqual([span.start, span.end], [540, 570]);
});

test("frameOf: пустой день — 08:00–22:00", async () => {
	const { frameOf } = await import(MODEL);
	const frame = frameOf(view([]));
	assert.deepEqual([frame.start, frame.end], [480, 1320]);
});

test("frameOf: день только с all_day — 08:00–22:00", async () => {
	const { frameOf } = await import(MODEL);
	const frame = frameOf(view([row("00:00", "23:59", { all_day: true })]));
	assert.deepEqual([frame.start, frame.end], [480, 1320]);
});

test("newSpan: клик в 23:50 у конца суток — 23:30–24:00", async () => {
	const { newSpan } = await import(MODEL);
	const span = newSpan(1430, { start: 1080, end: 1440 });
	assert.deepEqual([span.start, span.end], [1410, 1440]);
});

test("newSpan: клик ровно в 24:00 — 23:30–24:00", async () => {
	const { newSpan } = await import(MODEL);
	const span = newSpan(1440, { start: 1080, end: 1440 });
	assert.deepEqual([span.start, span.end], [1410, 1440]);
});

test("newSpan: frame.end не ограничивает конец", async () => {
	const { newSpan } = await import(MODEL);
	const span = newSpan(830, { start: 480, end: 840 });
	assert.deepEqual([span.start, span.end], [830, 860]);
});

test("dragOutcome move: конец ровно в 24:00 — полночь следующего дня", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("move", row("22:00", "23:00"), 60);
	assert.deepEqual(out, { start_at: at("23:00"), end_at: "2026-11-10T00:00:00" });
});

test("dragOutcome move: вниз за 00:00 — начало 00:00 этого дня, длительность та же", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("move", row("00:30", "01:30"), -120);
	assert.deepEqual(out, { start_at: at("00:00"), end_at: at("01:00") });
});

test("dragOutcome move: вверх за 24:00 — конец ровно 24:00 этого дня, длительность та же", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("move", row("22:00", "23:00"), 180);
	assert.deepEqual(out, { start_at: at("23:00"), end_at: "2026-11-10T00:00:00" });
});

test("dragOutcome resize: за 24:00 — конец 24:00 этого дня", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("resize", row("22:00", "23:00"), 180);
	assert.deepEqual(out, { start_at: at("22:00"), end_at: "2026-11-10T00:00:00" });
});

const OVERNIGHT = { id: 1, start_at: at("23:00"), end_at: "2026-11-10T01:00:00", all_day: false, repeat: null };

test("dragOutcome move: событие через полночь вперёд не двигается", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("move", OVERNIGHT, 5);
	assert.deepEqual(out, { start_at: at("23:00"), end_at: "2026-11-10T01:00:00" });
});

test("dragOutcome resize: конец через полночь не обрезается до 24:00", async () => {
	const { dragOutcome } = await import(MODEL);
	const out = dragOutcome("resize", OVERNIGHT, 5);
	assert.deepEqual(out, { start_at: at("23:00"), end_at: "2026-11-10T01:00:00" });
});

const SPAN = { start_at: at("10:00"), end_at: at("10:30") };

test("KINDS: порядок, подписи и слова видов", async () => {
	const { KINDS } = await import(MODEL);
	assert.deepEqual(KINDS, [
		{ value: "task", label: "задача", word: "Задача" },
		{ value: "focus", label: "фокус", word: "Фокус" },
		{ value: "rest", label: "отдых", word: "Прогулка / отдых" },
		{ value: "meal", label: "еда", word: "Перекус" },
		{ value: "checkin", label: "чек-ин", word: "Чек-ин" },
	]);
});

test("SURVEYS: значения опросников и подписи кнопок", async () => {
	const { SURVEYS } = await import(MODEL);
	assert.deepEqual(SURVEYS.map((item) => item.value), ["evening", "feel", "focus", "none"]);
	assert.ok(SURVEYS.every((item) => typeof item.label === "string" && item.label !== ""));
});

test("createPayload: у чек-ина survey, у задачи нет", async () => {
	const { createPayload } = await import(MODEL);
	const body = createPayload({ kind: "checkin", survey: "feel", title: "Оценка", ...SPAN });
	assert.deepEqual(body, { action: "create", kind: "checkin", survey: "feel", title: "Оценка", ...SPAN });
	const task = createPayload({ kind: "task", category: "work", survey: "feel", title: "x", ...SPAN });
	assert.equal("survey" in task, false);
});

test("createPayload: чек-ин без названия — «Чек-ин»", async () => {
	const { createPayload } = await import(MODEL);
	assert.equal(createPayload({ kind: "checkin", survey: "none", title: "", ...SPAN }).title, "Чек-ин");
});

test("CATEGORIES: порядок категорий задачи", async () => {
	const { CATEGORIES } = await import(MODEL);
	assert.deepEqual(CATEGORIES, ["work", "personal", "hobby"]);
});

test("createPayload: задача с названием и категорией", async () => {
	const { createPayload } = await import(MODEL);
	const body = createPayload({ kind: "task", category: "hobby", title: "Письмо", ...SPAN });
	assert.deepEqual(body, { action: "create", kind: "task", category: "hobby", title: "Письмо", ...SPAN });
});

test("createPayload: пустое название — слово вида", async () => {
	const { createPayload } = await import(MODEL);
	const words = { task: "Задача", focus: "Фокус", rest: "Прогулка / отдых", meal: "Перекус" };
	for (const [kind, word] of Object.entries(words)) {
		assert.equal(createPayload({ kind, category: "work", title: "", ...SPAN }).title, word);
	}
});

test("createPayload: название из пробелов — слово вида", async () => {
	const { createPayload } = await import(MODEL);
	assert.equal(createPayload({ kind: "focus", title: "   ", ...SPAN }).title, "Фокус");
});

test("createPayload: category только у задачи", async () => {
	const { createPayload } = await import(MODEL);
	assert.equal(createPayload({ kind: "task", category: "work", title: "", ...SPAN }).category, "work");
	for (const kind of ["focus", "rest", "meal"]) {
		const body = createPayload({ kind, category: "work", title: "x", ...SPAN });
		assert.equal("category" in body, false);
		assert.deepEqual(body, { action: "create", kind, title: "x", ...SPAN });
	}
});

test("locked: пункт с повтором заперт, обычный пункт нет", async () => {
	const { locked } = await import(MODEL);
	assert.equal(locked(row("09:00", "10:00", { repeat: "weekly" })), true);
	assert.equal(locked(row("09:00", "10:00", { source: "item" })), false);
});

test("locked: встреча с editable не заперта (Р11 = 1)", async () => {
	const { locked } = await import(MODEL);
	assert.equal(locked(row("09:00", "10:00", { source: "meeting", editable: true })), false);
});

test("locked: встреча с editable false заперта", async () => {
	const { locked } = await import(MODEL);
	assert.equal(locked(row("09:00", "10:00", { source: "meeting", editable: false })), true);
});

test("locked: повторяющаяся встреча, editable, не заперта (Р8 = 1)", async () => {
	const { locked } = await import(MODEL);
	assert.equal(locked(row("09:00", "10:00", { source: "meeting", editable: true, recurring: true })), false);
});

test("locked: пункт с повтором заперт и при editable", async () => {
	const { locked } = await import(MODEL);
	assert.equal(locked(row("09:00", "10:00", { source: "item", repeat: "weekly", editable: true })), true);
});

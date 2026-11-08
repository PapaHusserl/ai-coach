import test from "node:test";
import assert from "node:assert/strict";
import {
	FIELDS,
	TAB_LABELS,
	buildPayload,
	canSave,
	errorText,
	foodSummary,
	historyRows,
	isFuture,
	isPast,
	markSummary,
	remainingText,
	tabsFor,
} from "../../src/ai_coach/web/static/marks.js";

const empty = { ratings: [], feel: [], slips: [], done: null, food: [] };

const left = (extra) => ({ kcal: 800, protein_g: 40, fat_g: 20, carbs_g: 90, pending_count: 0, ...extra });

test("remainingText: цели нет", () => {
	assert.equal(remainingText({ remaining: null, food: [] }), "Цель на день не задана.");
});

test("remainingText: остаток, без «без КБЖУ» при pending_count 0", () => {
	assert.equal(
		remainingText({ remaining: left(), food: [] }),
		"Осталось на день 800 ккал · белок 40 г · жир 20 г · углеводы 90 г",
	);
});

test("remainingText: перебор по ккал", () => {
	const text = remainingText({ remaining: left({ kcal: -120 }), food: [] });
	assert.ok(text.startsWith("Перебор 120 ккал · белок 40 г"));
});

test("remainingText: записи без КБЖУ — число в конце", () => {
	const text = remainingText({ remaining: left({ pending_count: 2 }), food: [] });
	assert.ok(text.endsWith(" · без КБЖУ: 2"));
});

test("remainingText: дробные значения округляются, знак — после округления", () => {
	const frac = { kcal: -0.4, protein_g: -0.9000000000000057, fat_g: 19.6000000000001, carbs_g: 89.5 };
	assert.equal(
		remainingText({ remaining: left(frac), food: [] }),
		"Осталось на день 0 ккал · белок -1 г · жир 20 г · углеводы 90 г",
	);
	assert.ok(remainingText({ remaining: left({ kcal: -0.6 }), food: [] }).startsWith("Перебор 1 ккал"));
});

test("canSave: еда — только непустой текст", () => {
	assert.equal(canSave("food", {}), false);
	assert.equal(canSave("food", { text: "   " }), false);
	assert.equal(canSave("food", { text: " омлет " }), true);
});

test("tabsFor по типам", () => {
	assert.deepEqual(tabsFor("task"), ["rating", "feel", "slip"]);
	assert.deepEqual(tabsFor("focus"), ["rating", "feel", "slip"]);
	assert.deepEqual(tabsFor("rest"), ["done", "feel", "slip"]);
	assert.deepEqual(tabsFor("practice"), ["done", "feel", "slip"]);
	assert.deepEqual(tabsFor("checkin"), ["checkin"]);
	assert.deepEqual(tabsFor("meal"), ["food", "feel", "slip"]);
	assert.deepEqual(tabsFor("sleep"), []);
});

test("TAB_LABELS.food — «Что съел»", () => {
	assert.equal(TAB_LABELS.food, "Что съел");
});

test("markSummary: еда — «съел»", () => {
	const food = [{ id: 1, text: "омлет", kcal: null, logged_at: "2026-11-08 08:30:00" }];
	assert.equal(markSummary({ ...empty, food }), "съел");
	assert.equal(markSummary({ ...empty, food: [] }), "");
});

test("markSummary: еда перед самочувствием, самочувствие не добавляется", () => {
	const food = [{ id: 1, text: "омлет", kcal: null, logged_at: "2026-11-08 08:30:00" }];
	const feel = [{ score: 4, logged_at: "2026-11-08 08:40:00" }];
	assert.equal(markSummary({ ...empty, food, feel }), "съел");
});

test("foodSummary: тексты записей пункта через запятую", () => {
	const row = (text) => ({ id: 1, text, kcal: null, logged_at: "2026-11-08 08:30:00" });
	assert.equal(foodSummary({ remaining: null, food: [row("омлет"), row("кофе")] }), "омлет, кофе");
	assert.equal(foodSummary({ remaining: null, food: [row("омлет")] }), "омлет");
});

test("buildPayload: вкладка food — mark food и текст, без чисел", () => {
	const form = { event_id: 5, date: "2026-11-08", text: "  омлет " };
	assert.deepEqual(buildPayload("food", form), {
		event_id: 5,
		date: "2026-11-08",
		mark: "food",
		text: "омлет",
	});
});

test("historyRows: запись еды стоит по времени среди отметок, вкладка food", () => {
	const marks = {
		...empty,
		food: [{ id: 1, text: "омлет", kcal: null, logged_at: "2026-11-08 08:30:00" }],
		feel: [{ score: 4, text: "", logged_at: "2026-11-08 08:40:00" }],
	};
	const rows = historyRows(marks);
	assert.deepEqual(rows.map((r) => [r.time, r.tab]), [["08:30", "food"], ["08:40", "feel"]]);
	assert.ok(rows[0].text.includes("омлет"));
});

test("foodSummary: записей нет — пусто", () => {
	assert.equal(foodSummary({ remaining: null, food: [] }), "");
});

test("isPast и isFuture по границам", () => {
	const row = { start_at: "2026-11-08T10:00:00", end_at: "2026-11-08T11:00:00" };
	assert.equal(isPast(row, "2026-11-08T11:00:00"), true);
	assert.equal(isPast(row, "2026-11-08T10:59:59"), false);
	assert.equal(isFuture(row, "2026-11-08T09:59:59"), true);
	assert.equal(isFuture(row, "2026-11-08T10:00:00"), false);
});

test("markSummary: оценка, сделал, пропустил, пусто", () => {
	const rating = { focus: 4, fatigue: 2, effort: 3 };
	assert.equal(markSummary({ ...empty, ratings: [rating] }), "4/2/3");
	assert.equal(markSummary({ ...empty, ratings: [{ focus: 1, fatigue: 1, effort: 1 }, rating] }), "4/2/3");
	assert.equal(markSummary({ ...empty, done: { done: 1, logged_at: "x" } }), "сделал");
	assert.equal(markSummary({ ...empty, done: { done: 0, logged_at: "x" } }), "пропустил");
	assert.equal(markSummary(empty), "");
});

test("markSummary: без оценки и «сделал» — последнее самочувствие, у оценки приоритет", () => {
	const feel = [{ score: 2 }, { score: 4 }];
	assert.equal(markSummary({ ...empty, feel }), "самочувствие 4");
	assert.equal(markSummary({ ...empty, feel, done: { done: 1, logged_at: "x" } }), "сделал");
	assert.equal(markSummary({ ratings: [], done: null, food: [] }), "");
});

test("markSummary: оценка важнее самочувствия", () => {
	const ratings = [{ focus: 4, fatigue: 2, effort: 3 }];
	assert.equal(markSummary({ ratings, done: null, food: [], feel: [{ score: 5 }] }), "4/2/3");
});

test("historyRows: все отметки по времени", () => {
	const marks = {
		ratings: [{ focus: 4, fatigue: 2, effort: 3, text: "", logged_at: "2026-11-08 11:00:00" }],
		feel: [{ score: 4, text: "бодро", mood: null, stress: null, logged_at: "2026-11-08 10:30:00" }],
		slips: [{ text: "бесит", logged_at: "2026-11-08 10:45:00" }],
		done: { done: 0, logged_at: "2026-11-08 09:15:00" },
		food: [],
	};
	assert.deepEqual(historyRows(marks), [
		{ time: "09:15", tab: "done", text: "Пропустил" },
		{ time: "10:30", tab: "feel", text: "Самочувствие 4 — бодро" },
		{ time: "10:45", tab: "slip", text: "Срыв — бесит" },
		{ time: "11:00", tab: "rating", text: "Оценка 4/2/3" },
	]);
	assert.deepEqual(historyRows(empty), []);
	const done = { ...empty, done: { done: 1, logged_at: "2026-11-08 09:15:00" } };
	assert.equal(historyRows(done)[0].text, "Сделал");
});

test("historyRows: запись чек-ина с настроением и стрессом, пустые не выводятся", () => {
	const feel = (extra) => ({
		...empty,
		feel: [{ score: 4, text: "", mood: null, stress: null, logged_at: "2026-11-08 20:00:00", ...extra }],
	});
	assert.equal(
		historyRows(feel({ mood: 3, stress: 2, text: "устал" }))[0].text,
		"Самочувствие 4, настроение 3, стресс 2 — устал",
	);
	assert.equal(historyRows(feel({ mood: 3 }))[0].text, "Самочувствие 4, настроение 3");
	assert.equal(historyRows(feel({ stress: 2 }))[0].text, "Самочувствие 4, стресс 2");
	assert.equal(historyRows(feel({}))[0].text, "Самочувствие 4");
});

test("у каждой шкалы FIELDS есть подпись и полюса", () => {
	for (const field of Object.values(FIELDS)) {
		assert.ok(field.label);
		assert.ok(field.low);
		assert.ok(field.high);
	}
	assert.equal(FIELDS.focus.low, "рассеян");
	assert.equal(FIELDS.effort.high, "через силу");
});

test("canSave: шкалы выбраны все", () => {
	assert.equal(canSave("rating", { focus: 4, fatigue: 2 }), false);
	assert.equal(canSave("rating", { focus: 4, fatigue: 2, effort: 3 }), true);
	assert.equal(canSave("feel", {}), false);
	assert.equal(canSave("slip", {}), true);
});

test("buildPayload: числа, пустой текст не уходит", () => {
	const base = { event_id: 7, date: "2026-11-08" };
	assert.deepEqual(buildPayload("rating", { ...base, focus: "4", fatigue: 2, effort: 3, text: "  " }), {
		...base,
		mark: "rating",
		focus: 4,
		fatigue: 2,
		effort: 3,
	});
	assert.deepEqual(buildPayload("feel", { ...base, score: 4, text: " ок " }), {
		...base,
		mark: "feel",
		score: 4,
		text: "ок",
	});
	assert.deepEqual(buildPayload("slip", { ...base, text: "бесит" }), { ...base, mark: "slip", text: "бесит" });
});

test("canSave чек-ина: нужно только самочувствие", () => {
	assert.equal(canSave("checkin", { mood: 3 }), false);
	assert.equal(canSave("checkin", { score: 4 }), true);
});

test("buildPayload checkin: пустые поля не уходят, часы — число", () => {
	const base = { event_id: 9, date: "2026-11-08" };
	assert.deepEqual(buildPayload("checkin", { ...base, score: 4, text: "" }), {
		...base,
		mark: "checkin",
		score: 4,
	});
	const full = buildPayload("checkin", {
		...base,
		score: 4,
		mood: 5,
		stress: null,
		thoughts: 2,
		work: "6,5",
		hobby: "0",
		rest: "",
		flow: 0,
		text: "ок",
	});
	assert.deepEqual(full, {
		...base,
		mark: "checkin",
		score: 4,
		mood: 5,
		thoughts: 2,
		work: 6.5,
		hobby: 0,
		flow: 0,
		text: "ок",
	});
	assert.equal("stress" in full, false);
	assert.equal("rest" in full, false);
	assert.equal("work" in buildPayload("checkin", { ...base, score: 3, work: "abc" }), false);
	assert.equal("flow" in buildPayload("checkin", { ...base, score: 3, flow: null }), false);
});

test("buildPayload done: 1, 0 и null", () => {
	const base = { event_id: 7, date: "2026-11-08" };
	assert.equal(buildPayload("done", { ...base, done: 1 }).done, 1);
	assert.equal(buildPayload("done", { ...base, done: 0 }).done, 0);
	assert.equal(buildPayload("done", { ...base, done: null }).done, null);
});

test("errorText: про пункт — текст сервера, остальное — ошибка пульта", () => {
	assert.equal(errorText(400, "Пункт ещё не начался."), "Пункт ещё не начался.");
	assert.equal(errorText(400, "Текст не может быть пустым."), "Текст не может быть пустым.");
	assert.equal(
		errorText(400, "У этого пункта пока нет окна отметок."),
		"У этого пункта пока нет окна отметок.",
	);
	assert.equal(
		errorText(400, "У этого пункта нет такой отметки."),
		"Не сохранилось, ошибка пульта (код 400).",
	);
	assert.equal(errorText(400, "Пункта в этот день нет."), "Пункта в этот день нет.");
	assert.equal(errorText(400, "Часы (work) должны быть числом от 0 до 24."), "Часы (work) должны быть числом от 0 до 24.");
	assert.equal(errorText(400, "focus: от 1 до 5."), "Не сохранилось, ошибка пульта (код 400).");
	assert.equal(errorText(403, "Запись только со страницы пульта."), "Не сохранилось, ошибка пульта (код 403).");
	assert.equal(errorText(404, "Пункта нет."), "Не сохранилось, ошибка пульта (код 404).");
	assert.equal(errorText(400, "Пункт ещё не начался."), "Пункт ещё не начался.");
	assert.equal(errorText(0, ""), "Не сохранилось, ошибка пульта (код 0).");
});

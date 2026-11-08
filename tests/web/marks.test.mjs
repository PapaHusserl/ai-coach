import test from "node:test";
import assert from "node:assert/strict";
import {
	FIELDS,
	buildPayload,
	canSave,
	errorText,
	historyRows,
	isFuture,
	isPast,
	markSummary,
	tabsFor,
} from "../../src/ai_coach/web/static/marks.js";

const empty = { ratings: [], feel: [], slips: [], done: null };

test("tabsFor по типам", () => {
	assert.deepEqual(tabsFor("task"), ["rating", "feel", "slip"]);
	assert.deepEqual(tabsFor("focus"), ["rating", "feel", "slip"]);
	assert.deepEqual(tabsFor("rest"), ["done", "feel", "slip"]);
	assert.deepEqual(tabsFor("practice"), ["done", "feel", "slip"]);
	assert.deepEqual(tabsFor("checkin"), ["checkin"]);
	assert.deepEqual(tabsFor("meal"), []);
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

test("historyRows: все отметки по времени", () => {
	const marks = {
		ratings: [{ focus: 4, fatigue: 2, effort: 3, text: "", logged_at: "2026-11-08 11:00:00" }],
		feel: [{ score: 4, text: "бодро", mood: null, stress: null, logged_at: "2026-11-08 10:30:00" }],
		slips: [{ text: "бесит", logged_at: "2026-11-08 10:45:00" }],
		done: { done: 0, logged_at: "2026-11-08 09:15:00" },
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

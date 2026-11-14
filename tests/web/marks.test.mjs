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

test("tabsFor: чек-ин с опросником — одна вкладка своего опросника", () => {
	assert.deepEqual(tabsFor("checkin", "evening"), ["checkin"]);
	assert.deepEqual(tabsFor("checkin", "feel"), ["feel"]);
	assert.deepEqual(tabsFor("checkin", "focus"), ["rating"]);
	assert.deepEqual(tabsFor("checkin", "none"), ["done"]);
});

test("tabsFor: чек-ин без опросника (null) — вечерний", () => {
	assert.deepEqual(tabsFor("checkin", null), ["checkin"]);
	assert.deepEqual(tabsFor("checkin", undefined), ["checkin"]);
});

test("tabsFor: опросник у не-чек-ина не действует", () => {
	assert.deepEqual(tabsFor("task", "feel"), ["rating", "feel", "slip"]);
	assert.deepEqual(tabsFor("practice", "none"), ["done", "feel", "slip"]);
});

test("tabLabel: у чек-ина done — «Сделал», не «Итог»", async () => {
	const { tabLabel } = await model();
	assert.equal(tabLabel("checkin", "done"), "Сделал");
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

// Партия 4: имена новые — импорт внутри теста, чтобы остальные тесты файла собирались.
const model = () => import("../../src/ai_coach/web/static/marks.js");

test("tabsFor: тренировка — сделал, самочувствие, срыв", () => {
	assert.deepEqual(tabsFor("training"), ["done", "feel", "slip"]);
});

test("zoneShares: доли в проценты Z1..Z5, нулевые зоны пропущены", async () => {
	const { zoneShares } = await model();
	const rows = zoneShares({ zones: [0.5, 0.3, 0.2, 0, 0] });
	assert.deepEqual(
		rows.map((r) => [r.name, r.percent]),
		[
			["Z1", 50],
			["Z2", 30],
			["Z3", 20],
		],
	);
});

test("zoneShares: проценты округляются", async () => {
	const { zoneShares } = await model();
	const rows = zoneShares({ zones: [0.126, 0, 0, 0, 0.874] });
	assert.deepEqual(
		rows.map((r) => [r.name, r.percent]),
		[
			["Z1", 13],
			["Z5", 87],
		],
	);
});

test("zoneShares: зон нет (null) — пусто", async () => {
	const { zoneShares } = await model();
	assert.deepEqual(zoneShares({ zones: null }), []);
});

test("planFactRows: строки с знаком ✓ у ok и ! у warn", async () => {
	const { planFactRows } = await model();
	const training = {
		fact: {
			rows: [
				{ label: "Длительность", plan: "45 мин", fact: "44 мин", mark: "ok" },
				{ label: "Темп", plan: "5:30 /км - 5:00 /км", fact: "6:00 /км", mark: "warn" },
			],
		},
	};
	assert.deepEqual(planFactRows(training), [
		{ label: "Длительность", plan: "45 мин", fact: "44 мин", mark: "ok", sign: "✓" },
		{ label: "Темп", plan: "5:30 /км - 5:00 /км", fact: "6:00 /км", mark: "warn", sign: "!" },
	]);
});

test("planFactRows: факта нет — пусто", async () => {
	const { planFactRows } = await model();
	assert.deepEqual(planFactRows({ plan: {}, fact: null }), []);
	assert.deepEqual(planFactRows({ plan: {}, fact: { rows: [] } }), []);
});

test("stepText: тип шага словами и минуты", async () => {
	const { stepText } = await model();
	assert.equal(stepText({ k: "warmup", sec: 300 }), "разминка 5 мин");
	assert.equal(stepText({ k: "cooldown", sec: 600 }), "заминка 10 мин");
});

test("stepText: название шага вместо типа", async () => {
	const { stepText } = await model();
	assert.equal(stepText({ k: "work", t: "Лёгкий бег", sec: 1200 }), "Лёгкий бег 20 мин");
});

test("stepText: шаг в метрах — километры", async () => {
	const { stepText } = await model();
	assert.match(stepText({ k: "work", m: 1000 }), /1 км/);
});

test("stepText: подходы силового — повторы и вес", async () => {
	const { stepText } = await model();
	const text = stepText({ k: "work", reps: 12, kg: 20 });
	assert.match(text, /12/);
	assert.match(text, /20 кг/);
});

const doneFact = {
	kind: "done",
	duration_s: 2460,
	distance_m: 6000,
	pace_s_km: 410,
	avg_hr: 140.4,
	training_load: 55.6,
	calories: 300,
};

test("tabLabel: у тренировки done — «Итог», у практики — «Сделал»", async () => {
	const { tabLabel } = await model();
	assert.equal(tabLabel("training", "done"), "Итог");
	assert.equal(tabLabel("practice", "done"), "Сделал");
	assert.equal(tabLabel("training", "feel"), "Самочувствие");
});

test("stepRows: блок с повторами — «3 × …», название блока вместо типа", async () => {
	const { stepRows } = await model();
	const blocks = [
		{ r: 1, s: [{ k: "warmup", sec: 300 }] },
		{ r: 3, t: "Присед", s: [{ k: "work", reps: 5, kg: 60 }, { k: "rest", sec: 90 }] },
	];
	assert.deepEqual(stepRows(blocks), [
		"разминка 5 мин",
		"3 × Присед 5 × 60 кг",
		"3 × отдых 1 мин 30 с",
	]);
});

test("factNumbers: шесть чисел с единицами", async () => {
	const { factNumbers } = await model();
	assert.deepEqual(
		factNumbers(doneFact).map((n) => [n.label, n.value]),
		[
			["Время", "41 мин"],
			["Дистанция", "6.0 км"],
			["Темп", "6:50 /км"],
			["Пульс ср.", 140],
			["Нагрузка", 56],
			["Ккал", 300],
		],
	);
});

test("factNumbers: час и больше, пустое поле — прочерк", async () => {
	const { factNumbers } = await model();
	const rows = factNumbers({ ...doneFact, duration_s: 3900, avg_hr: null });
	assert.equal(rows[0].value, "1 ч 5 мин");
	assert.equal(rows[3].value, "—");
});

test("factNumbers: дистанция 0 — прочерк, как на сервере", async () => {
	const { factNumbers } = await model();
	const rows = factNumbers({ ...doneFact, distance_m: 0 });
	assert.equal(rows[1].value, "—");
});

test("stepText: точные строки — темп бегового шага, метры, секунды, повторы, вес", async () => {
	const { stepText } = await model();
	assert.equal(stepText({ k: "work", m: 1000, pace: [300, 330] }), "работа 1 км 5:30 - 5:00 /км");
	assert.equal(stepText({ k: "work", m: 1500 }), "работа 1.5 км");
	assert.equal(stepText({ k: "work", m: 400 }), "работа 400 м");
	assert.equal(stepText({ k: "rest", sec: 45 }), "отдых 45 с");
	assert.equal(stepText({ k: "work", reps: 12 }), "работа 12 повт.");
	assert.equal(stepText({ k: "work", kg: 20, sec: 30 }), "работа 30 с 20 кг");
	assert.equal(stepText({ k: "work", reps: 5, kg: 60 }, "Присед"), "Присед 5 × 60 кг");
});

test("factNumbers: пропуск без активности — пусто", async () => {
	const { factNumbers } = await model();
	assert.deepEqual(factNumbers({ kind: "skipped", duration_s: null, distance_m: null }), []);
});

test("factPill: три вида по Р20", async () => {
	const { factPill } = await model();
	assert.deepEqual(factPill({ kind: "done" }), { text: "✓ выполнено по плану", tone: "good" });
	assert.deepEqual(factPill({ kind: "different" }), { text: "выполнено иначе", tone: "warn" });
	assert.deepEqual(factPill({ kind: "skipped" }), { text: "пропущено", tone: "muted" });
});

test("markSummary: факт done без отметки — «✓ по плану»", () => {
	assert.equal(markSummary(empty, { kind: "done" }), "✓ по плану");
});

test("markSummary: факт different — «выполнено иначе», skipped — без слов", () => {
	assert.equal(markSummary(empty, { kind: "different" }), "выполнено иначе");
	assert.equal(markSummary(empty, { kind: "skipped" }), "");
});

test("markSummary: отметка важнее факта", () => {
	const marks = { ...empty, done: { done: 0, logged_at: "2026-11-07 11:00:00" } };
	assert.equal(markSummary(marks, { kind: "done" }), "пропустил");
});

test("missingText: названия через запятую, пусто — пустая строка", async () => {
	const { missingText } = await model();
	assert.equal(missingText({ missing: ["Присед", "Тяга"] }), "Не сделано: Присед, Тяга");
	assert.equal(missingText({ missing: [] }), "");
	assert.equal(missingText({ missing: null }), "");
});

// Партия 6: варианты блюд.
const ITEM = (kcal, protein_g, fat_g, carbs_g) => ({ what: "x", qty: "1", kcal, protein_g, fat_g, carbs_g });

test("offerTotals: суммы строк варианта", async () => {
	const { offerTotals } = await model();
	const offer = { items: [ITEM(150, 12, 10, 1), ITEM(120, 4, 1, 24)] };
	assert.deepEqual(offerTotals(offer), { kcal: 270, protein_g: 16, fat_g: 11, carbs_g: 25 });
});

test("offerTotals: пустой вариант — нули", async () => {
	const { offerTotals } = await model();
	assert.deepEqual(offerTotals({ items: [] }), { kcal: 0, protein_g: 0, fat_g: 0, carbs_g: 0 });
});

test("offerRows: подвал — Итого и Останется на день, четыре числа", async () => {
	const { offerRows } = await model();
	const offer = { items: [ITEM(150, 12, 10, 1), ITEM(120.5, 4, 1, 24)] };
	const remaining = { kcal: 800, protein_g: 40, fat_g: 20, carbs_g: 90 };
	const { rows, foot } = offerRows(offer, remaining);
	assert.deepEqual(rows, [
		["x", "1", "150", "12", "10", "1"],
		["x", "1", "120.5", "4", "1", "24"],
	]);
	assert.deepEqual(foot, [
		["Итого", "", "270.5", "16", "11", "25"],
		["Останется на день", "", "529.5", "24", "9", "65"],
	]);
});

test("offerRows: цели нет — в подвале только Итого", async () => {
	const { offerRows } = await model();
	const { foot } = offerRows({ items: [ITEM(150, 12, 10, 1)] }, null);
	assert.deepEqual(foot, [["Итого", "", "150", "12", "10", "1"]]);
});

test("buildPayload: еда по варианту — offer_id числом, текста нет", () => {
	const form = { event_id: 5, date: "2026-11-07", offer_id: 3 };
	assert.deepEqual(buildPayload("food", form), {
		event_id: 5,
		date: "2026-11-07",
		mark: "food",
		offer_id: 3,
	});
});

const MODEL = "../../src/ai_coach/web/static/marks-model.js";

test("screenHint: работа и хобби, браузер 0 — без хвоста", async () => {
	const { screenHint } = await import(MODEL);
	assert.equal(screenHint({ work: 4.2, hobby: 0.8, browser: 0 }), "экран: работа 4.2 ч · хобби 0.8 ч");
});

test("screenHint: браузер больше нуля — хвост с одним знаком", async () => {
	const { screenHint } = await import(MODEL);
	assert.equal(
		screenHint({ work: 4.2, hobby: 0.8, browser: 1.26 }),
		"экран: работа 4.2 ч · хобби 0.8 ч · браузер 1.3 ч",
	);
});

test("screenHint: целые часы без дроби", async () => {
	const { screenHint } = await import(MODEL);
	assert.equal(screenHint({ work: 4, hobby: 1, browser: 0 }), "экран: работа 4 ч · хобби 1 ч");
});

test("screenHint: причины отсутствия данных", async () => {
	const { screenHint } = await import(MODEL);
	assert.equal(screenHint({ missing: "config" }), "экран: не настроен");
	assert.equal(screenHint({ missing: "silent" }), "экран: ActivityWatch не отвечает");
	assert.equal(screenHint({ missing: "empty" }), "экран: за день пусто");
});

test("screenFill: один знак после запятой", async () => {
	const { screenFill } = await import(MODEL);
	assert.deepEqual(screenFill({ work: 4.19, hobby: 0.81, browser: 2 }), { work: 4.2, hobby: 0.8 });
});

test("screenFill + buildPayload checkin: подставленное уходит числом", async () => {
	const { screenFill } = await import(MODEL);
	const form = { event_id: 9, date: "2026-11-08", score: 4, ...screenFill({ work: 4.19, hobby: 0.81 }) };
	const payload = buildPayload("checkin", form);
	assert.equal(payload.work, 4.2);
	assert.equal(payload.hobby, 0.8);
	assert.equal("rest" in payload, false);
});

test("buildPayload: еда своим текстом — без offer_id", () => {
	const form = { event_id: 5, date: "2026-11-07", text: " борщ " };
	assert.deepEqual(buildPayload("food", form), {
		event_id: 5,
		date: "2026-11-07",
		mark: "food",
		text: "борщ",
	});
});

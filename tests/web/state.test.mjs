import test from "node:test";
import assert from "node:assert/strict";

// Партия 5 П4: вкладка «Состояние». Имена новые — импорт внутри теста.
const stateModel = () => import("../../src/ai_coach/web/static/state-model.js");

const TRENDS = {
	dates: ["2026-11-06", "2026-11-07"],
	sleep_h: [7.5, null],
	hrv: [60, 64],
	rhr: [50, 52],
	readiness: [70, null],
	weight: [
		{ date: "2026-10-20", kg: 83.1 },
		{ date: "2026-11-07", kg: 81.7 },
	],
};
const stateOf = (signals) => ({ signals, trends: TRENDS, load_error: null });
const SHORT = { source: "sleep", kind: "short_night", value: 2, limit: 1 };
const DEBT = { source: "sleep", kind: "sleep_debt", value: 3.5, limit: 3 };
const text = (row) => JSON.stringify(row);

test("SIGNAL_WORDS: слова из справки (Р10 = 1)", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.short_night, "короткая ночь");
	assert.equal(SIGNAL_WORDS.sleep_debt, "долг сна");
});

test("signalRows: сигналов нет — пустой список", async () => {
	const { signalRows } = await stateModel();
	assert.deepEqual(signalRows(stateOf([])), []);
});

test("signalRows: по строке на сигнал, порядок сервера", async () => {
	const { signalRows } = await stateModel();
	const rows = signalRows(stateOf([SHORT, DEBT]));
	assert.equal(rows.length, 2);
	assert.ok(text(rows[0]).includes("короткая ночь"));
	assert.ok(text(rows[1]).includes("долг сна"));
});

test("signalRows: строка несёт value и limit", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([DEBT]));
	assert.ok(text(row).includes("3.5"));
	assert.ok(text(row).includes("3"));
});

test("trendSeries: пять рядов — сон, HRV, пульс покоя, готовность, вес", async () => {
	const { trendSeries } = await stateModel();
	const keys = trendSeries(stateOf([])).map((series) => series.key);
	assert.deepEqual(keys, ["sleep_h", "hrv", "rhr", "readiness", "weight"]);
});

test("trendSeries: значения ряда как в ответе сервера", async () => {
	const { trendSeries } = await stateModel();
	const hrv = trendSeries(stateOf([])).find((series) => series.key === "hrv");
	assert.deepEqual(hrv.values, [60, 64]);
});

test("trendSeries: вес — числа kg", async () => {
	const { trendSeries } = await stateModel();
	const weight = trendSeries(stateOf([])).find((series) => series.key === "weight");
	assert.deepEqual(weight.values, [83.1, 81.7]);
});

const CODES = [
	"short_night", "sleep_debt", "illness_risk", "corridor_out", "total_streak", "evening_streak", "weekend_work",
	"recovery_drop", "todo_growth", "who5_low", "who5_reduced", "who5_drop", "wellbeing", "mood",
	"stress", "wellbeing_below", "mood_below", "symptoms", "fever", "readiness", "hrv", "sleep", "atl_over_ctl",
	"illness_rest", "illness_return", "hrv_streak", "illness_light", "fatigue", "irritability",
	"pressure_drop", "temperature_rise", "temperature_drop", "no_day_off",
];

test("SIGNAL_WORDS: no_day_off — «нет полного выходного» (Н7, Р10а = 1)", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.no_day_off, "нет полного выходного");
});

test("signalRows: no_day_off — слово и «9 (порог 7)»", async () => {
	const { signalRows } = await stateModel();
	const row = { source: "overload", kind: "no_day_off", value: 9, limit: 7 };
	const [found] = signalRows(stateOf([row]));
	assert.ok(text(found).includes("нет полного выходного"));
	assert.ok(text(found).includes("9 (порог 7)"));
});

test("SIGNAL_WORDS: слабый сигнал первого дня — «пульс или HRV вне нормы»", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.corridor_out, "пульс или HRV вне нормы");
});

test("signalRows: corridor_out — слово и «1 (порог 2)»", async () => {
	const { signalRows } = await stateModel();
	const row = { source: "illness", kind: "corridor_out", value: 1, limit: 2 };
	const [found] = signalRows(stateOf([row]));
	assert.ok(text(found).includes("пульс или HRV вне нормы"));
	assert.ok(text(found).includes("1 (порог 2)"));
});

test("SIGNAL_WORDS: ровно 33 кода отчётов", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.deepEqual(Object.keys(SIGNAL_WORDS).sort(), [...CODES].sort());
});

// Н38, партия 2, Р8 = 1: новые строки и пометка «вчера вечером» у перенесённых (ключ day).
const DEVIATION = { source: "deviations", value: 4, limit: 4 };

test("signalRows: усталость · 4 (порог 4)", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ ...DEVIATION, kind: "fatigue" }]));
	assert.equal(row.word, "усталость");
	assert.equal(row.detail, "4 (порог 4)");
});

test("signalRows: раздражительность · 4 (порог 4)", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ ...DEVIATION, kind: "irritability" }]));
	assert.equal(row.word, "раздражительность");
	assert.equal(row.detail, "4 (порог 4)");
});

test("signalRows: строка с day — «вчера вечером: настроение», деталь прежняя", async () => {
	const { signalRows } = await stateModel();
	const carried = { source: "deviations", kind: "mood", value: 2, limit: 2, day: "2026-11-06" };
	const [row] = signalRows(stateOf([carried]));
	assert.equal(row.word, "вчера вечером: настроение");
	assert.equal(row.detail, "2 (порог 2)");
});

test("signalRows: mood_below с day — «вчера вечером: настроение ниже нормы», норма 4", async () => {
	const { signalRows } = await stateModel();
	const carried = { source: "deviations", kind: "mood_below", value: 3, limit: 4, day: "2026-11-06" };
	const [row] = signalRows(stateOf([carried]));
	assert.equal(row.word, "вчера вечером: настроение ниже нормы");
	assert.equal(row.detail, "3 (норма 4)");
});

test("signalRows: у сегодняшней строки пометки «вчера вечером» нет", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ ...DEVIATION, kind: "stress" }]));
	assert.equal(row.word, "стресс");
});

test("signalRows: порядок сервера — перенесённые после сегодняшних", async () => {
	const { signalRows } = await stateModel();
	const carried = { source: "deviations", kind: "stress", value: 5, limit: 4, day: "2026-11-06" };
	const rows = signalRows(stateOf([{ ...DEVIATION, kind: "fatigue" }, carried]));
	assert.deepEqual(rows.map((row) => row.word), ["усталость", "вчера вечером: стресс"]);
});

test("SIGNAL_WORDS: слова Р10 = 1", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.illness_risk, "возможно, заболеваешь");
	assert.equal(SIGNAL_WORDS.who5_low, "WHO-5 низкий");
	assert.equal(SIGNAL_WORDS.atl_over_ctl, "ATL выше CTL");
	assert.equal(SIGNAL_WORDS.sleep, "сон");
});

test("signalRows: неизвестный код — слово равно коду", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ source: "sleep", kind: "x", value: 1, limit: 2 }]));
	assert.equal(row.word, "x");
});

test("trendSeries: подписи рядов (Р11 = 1)", async () => {
	const { trendSeries } = await stateModel();
	const labels = trendSeries(stateOf([])).map((series) => series.label);
	assert.deepEqual(labels, ["сон, ч", "HRV", "пульс покоя", "готовность", "вес, кг"]);
});

test("trendSeries: даты четырёх рядов — trends.dates, у веса — даты записей", async () => {
	const { trendSeries } = await stateModel();
	const byKey = Object.fromEntries(trendSeries(stateOf([])).map((series) => [series.key, series]));
	assert.deepEqual(byKey.hrv.dates, TRENDS.dates);
	assert.deepEqual(byKey.sleep_h.dates, TRENDS.dates);
	assert.deepEqual(byKey.weight.dates, ["2026-10-20", "2026-11-07"]);
});

// Р23 = 1: detail — «<value> (порог <limit>)»; список через запятую, словарь — «ключ значение».
const detailOf = async (signal) => {
	const { signalRows } = await stateModel();
	return signalRows(stateOf([signal]))[0].detail;
};

test("detail: числа — «3.5 (порог 3)»", async () => {
	assert.equal(await detailOf(DEBT), "3.5 (порог 3)");
});

test("detail: целые числа — «2 (порог 1)»", async () => {
	assert.equal(await detailOf(SHORT), "2 (порог 1)");
});

test("detail: строка как есть, список порога через запятую", async () => {
	const hrv = { source: "deviations", kind: "hrv", value: "LOW", limit: ["LOW", "UNBALANCED", "BELOW"] };
	assert.equal(await detailOf(hrv), "LOW (порог LOW, UNBALANCED, BELOW)");
});

test("detail: словарь — «ключ значение» через запятую", async () => {
	const drop = {
		source: "overload",
		kind: "recovery_drop",
		value: { readiness: 12, mood: 1.5 },
		limit: { readiness: 10, mood: 1, stress: 1 },
	};
	assert.equal(await detailOf(drop), "readiness 12, mood 1.5 (порог readiness 10, mood 1, stress 1)");
});

test("SIGNAL_WORDS: symptoms — «симптомы»", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.symptoms, "симптомы");
});

test("SIGNAL_WORDS: fever — «температура»", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.fever, "температура");
});

test("signalRows: fever — «температура · 37.2 (порог 37)», порог без «.0»", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ source: "deviations", kind: "fever", value: 37.2, limit: 37.0 }]));
	assert.equal(row.word, "температура");
	assert.ok(text(row).includes("37.2 (порог 37)"), text(row));
});

test("detail: symptoms — слова через запятую, без порога", async () => {
	const symptoms = { source: "deviations", kind: "symptoms", value: ["горло", "насморк"], limit: null };
	const detail = await detailOf(symptoms);
	assert.equal(detail, "горло, насморк");
	assert.ok(!detail.includes("порог"));
});

test("signalRows: symptoms — слово строки «симптомы»", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ source: "deviations", kind: "symptoms", value: ["горло"], limit: null }]));
	assert.equal(row.word, "симптомы");
});

// Н33, партия 2б: покой и возврат после болезни; причина незачёта — хвостом после тире (Р18 = 2).
const rowOf = async (signal) => {
	const { signalRows } = await stateModel();
	return signalRows(stateOf([{ source: "illness", ...signal }]))[0];
};

test("signalRows: illness_rest без причин — «покой после болезни · день 2 из 2»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 2, limit: 2, why: [] });
	assert.equal(row.word, "покой после болезни");
	assert.equal(row.detail, "день 2 из 2");
});

test("signalRows: illness_rest с «нет записи» — «день 1 из 2 — нет записи»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["no_record"] });
	assert.equal(row.detail, "день 1 из 2 — нет записи");
});

test("signalRows: illness_rest без поля why — хвоста нет", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2 });
	assert.equal(row.detail, "день 1 из 2");
});

test("signalRows: no_night — «нет ночи с часов»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["no_night"] });
	assert.equal(row.detail, "день 1 из 2 — нет ночи с часов");
});

test("signalRows: corridor — «пульс или HRV вне нормы»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["corridor"] });
	assert.equal(row.detail, "день 1 из 2 — пульс или HRV вне нормы");
});

test("signalRows: две живые причины — через запятую в порядке сервера", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["no_record", "corridor"] });
	assert.equal(row.detail, "день 1 из 2 — нет записи, пульс или HRV вне нормы");
});

test("REASON_WORDS: corridor — то же слово, что у corridor_out", async () => {
	const { REASON_WORDS, SIGNAL_WORDS } = await stateModel();
	assert.equal(REASON_WORDS.corridor, SIGNAL_WORDS.corridor_out);
});

test("REASON_WORDS: ровно шесть кодов причин", async () => {
	const { REASON_WORDS } = await stateModel();
	assert.deepEqual(
		Object.keys(REASON_WORDS).sort(),
		["corridor", "no_night", "no_record", "respiration", "skin_temp", "spo2"],
	);
});

// Н33, партия 3: серия статуса HRV и метрики ночи.
test("SIGNAL_WORDS: hrv_streak — «статус HRV плохой подряд»", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.hrv_streak, "статус HRV плохой подряд");
});

test("signalRows: hrv_streak — «3 (порог 2)»", async () => {
	const { signalRows } = await stateModel();
	const row = { source: "illness", kind: "hrv_streak", value: 3, limit: 2 };
	const [found] = signalRows(stateOf([row]));
	assert.equal(found.word, "статус HRV плохой подряд");
	assert.equal(found.detail, "3 (порог 2)");
});

test("signalRows: skin_temp — «температура кожи выше нормы»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["skin_temp"] });
	assert.equal(row.detail, "день 1 из 2 — температура кожи выше нормы");
});

test("signalRows: respiration — «дыхание чаще нормы»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["respiration"] });
	assert.equal(row.detail, "день 1 из 2 — дыхание чаще нормы");
});

test("signalRows: spo2 — «SpO2 ниже 92»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["spo2"] });
	assert.equal(row.detail, "день 1 из 2 — SpO2 ниже 92");
});

test("signalRows: нет записи и метрика ночи — через запятую", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["no_record", "spo2"] });
	assert.equal(row.detail, "день 1 из 2 — нет записи, SpO2 ниже 92");
});

test("signalRows: известная и неизвестная причина — через запятую, неизвестный код как есть", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["no_record", "zzz"] });
	assert.equal(row.detail, "день 1 из 2 — нет записи, zzz");
});

test("signalRows: порядок причин — как у сервера, не по алфавиту", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["zzz", "no_record"] });
	assert.equal(row.detail, "день 1 из 2 — zzz, нет записи");
});

test("signalRows: illness_return — «возврат после болезни · день 3 из 7», хвоста нет", async () => {
	const row = await rowOf({ kind: "illness_return", value: 3, limit: 7 });
	assert.equal(row.word, "возврат после болезни");
	assert.equal(row.detail, "день 3 из 7");
});

test("signalRows: у illness_return причины не дописываются, даже если why пришло", async () => {
	const row = await rowOf({ kind: "illness_return", value: 3, limit: 7, why: ["no_record"] });
	assert.equal(row.detail, "день 3 из 7");
});

// Н49, партия 1: слова при отметке COVID (Решения пп. 7, 8).
test("signalRows: покой при COVID, короткая серия — «покой после COVID · день болезни 3 из 5»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 3, limit: 5, why: [], covid: true, count: "series" });
	assert.equal(row.word, "покой после COVID");
	assert.equal(row.detail, "день болезни 3 из 5");
});

test("signalRows: покой при COVID, длинная серия — «покой после COVID · день 1 из 2 — нет записи»", async () => {
	const row = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["no_record"], covid: true });
	assert.equal(row.word, "покой после COVID");
	assert.equal(row.detail, "день 1 из 2 — нет записи");
});

test("signalRows: возврат при COVID — «возврат после COVID · день 1 из 7»", async () => {
	const row = await rowOf({ kind: "illness_return", value: 1, limit: 7, covid: true });
	assert.equal(row.word, "возврат после COVID");
	assert.equal(row.detail, "день 1 из 7");
});

test("signalRows: лёгкая серия при COVID — «лёгкий режим при COVID · день 2 из 5»", async () => {
	const row = await rowOf({ kind: "illness_light", value: 2, limit: 5, covid: true });
	assert.equal(row.word, "лёгкий режим при COVID");
	assert.equal(row.detail, "день 2 из 5");
});

test("SIGNAL_WORDS: illness_light — «лёгкий режим при COVID»", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.illness_light, "лёгкий режим при COVID");
});

test("signalRows: illness_light без ключа covid — то же слово и «день 2 из 5»", async () => {
	const row = await rowOf({ kind: "illness_light", value: 2, limit: 5 });
	assert.equal(row.word, "лёгкий режим при COVID");
	assert.equal(row.detail, "день 2 из 5");
});

test("signalRows: covid false — прежние слова покоя и возврата", async () => {
	const rest = await rowOf({ kind: "illness_rest", value: 1, limit: 2, why: ["no_record"], covid: false });
	assert.equal(rest.word, "покой после болезни");
	assert.equal(rest.detail, "день 1 из 2 — нет записи");
	const back = await rowOf({ kind: "illness_return", value: 3, limit: 7, covid: false });
	assert.equal(back.word, "возврат после болезни");
});

test("signalRows: у других сигналов поле why хвоста не даёт", async () => {
	const row = await rowOf({ kind: "short_night", value: 2, limit: 1, why: ["no_record"] });
	assert.equal(row.detail, "2 (порог 1)");
});

test("signalRows: неизвестный код сигнала по-прежнему как есть", async () => {
	const row = await rowOf({ kind: "illness_unknown", value: 1, limit: 2 });
	assert.equal(row.word, "illness_unknown");
});

test("SIGNAL_WORDS: ниже своей нормы — самочувствие и настроение", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.wellbeing_below, "самочувствие ниже нормы");
	assert.equal(SIGNAL_WORDS.mood_below, "настроение ниже нормы");
});

test("detail: mood_below — «3 (норма 4)»", async () => {
	const mood = { source: "deviations", kind: "mood_below", value: 3, limit: 4 };
	assert.equal(await detailOf(mood), "3 (норма 4)");
});

test("detail: wellbeing_below — «3 (норма 4.5)», без «порог»", async () => {
	const score = { source: "deviations", kind: "wellbeing_below", value: 3, limit: 4.5 };
	const detail = await detailOf(score);
	assert.equal(detail, "3 (норма 4.5)");
	assert.ok(!detail.includes("порог"));
});

test("detail: у остальных кодов «(порог …)» как раньше, не «норма»", async () => {
	const detail = await detailOf({ source: "deviations", kind: "mood", value: 2, limit: 2 });
	assert.equal(detail, "2 (порог 2)");
});

test("signalRows: source не попадает в detail", async () => {
	assert.ok(!(await detailOf(SHORT)).includes("sleep"));
});

// Р24 = 1: шкала Y от минимума до максимума ряда без null.
const chartModule = () => import("../../src/ai_coach/web/static/chart.js");

test("valueRange: минимум и максимум, null не считаются", async () => {
	const { valueRange } = await chartModule();
	assert.deepEqual(valueRange([60, 64, null]), { min: 60, max: 64 });
});

test("valueRange: null посередине и в начале не влияют", async () => {
	const { valueRange } = await chartModule();
	assert.deepEqual(valueRange([null, 70, null, 55, 62]), { min: 55, max: 70 });
});

test("valueRange: ровный ряд — плюс-минус один", async () => {
	const { valueRange } = await chartModule();
	assert.deepEqual(valueRange([5, 5]), { min: 4, max: 6 });
});

test("valueRange: одно значение — плюс-минус один", async () => {
	const { valueRange } = await chartModule();
	assert.deepEqual(valueRange([5, null]), { min: 4, max: 6 });
});

test("valueRange: только null — нет шкалы", async () => {
	const { valueRange } = await chartModule();
	assert.equal(valueRange([null]), null);
});

test("valueRange: пустой ряд — нет шкалы", async () => {
	const { valueRange } = await chartModule();
	assert.equal(valueRange([]), null);
});

// Р25 = 1: null разрывает линию, одиночное значение — отрезок из одной точки.
const SEG_BOX = { x0: 0, x1: 40, y0: 0, y1: 100, min: 0, max: 10 };

test("chartSegments: null разрывает ряд на два отрезка по одной точке", async () => {
	const { chartSegments } = await chartModule();
	assert.deepEqual(chartSegments([1, null, 3], { ...SEG_BOX, x1: 20 }), [
		[[0, 90]],
		[[20, 70]],
	]);
});

test("chartSegments: два отрезка по две точки, x по индексу во всём ряду", async () => {
	const { chartSegments } = await chartModule();
	assert.deepEqual(chartSegments([1, 2, null, 3, 4], SEG_BOX), [
		[
			[0, 90],
			[10, 80],
		],
		[
			[30, 70],
			[40, 60],
		],
	]);
});

test("chartSegments: только null — отрезков нет", async () => {
	const { chartSegments } = await chartModule();
	assert.deepEqual(chartSegments([null, null], SEG_BOX), []);
});

test("chartSegments: без пропусков — один отрезок, точки как у chartPoints", async () => {
	const { chartSegments, chartPoints } = await chartModule();
	const values = [2, 4, 6];
	assert.deepEqual(chartSegments(values, SEG_BOX), [chartPoints(values, SEG_BOX)]);
});

test("chartSegments: пропуск в начале и в конце не рисуется", async () => {
	const { chartSegments } = await chartModule();
	assert.deepEqual(chartSegments([null, 5, 5, null], { ...SEG_BOX, x1: 30 }), [
		[
			[10, 50],
			[20, 50],
		],
	]);
});

// П7, партия 9: сигнал погоды — слова, час, «порог», «завтра» (Р35 = 2, Р39 = 1, Р40 = 3, Р44 = 2).
const WEATHER = { source: "weather", value: 7.0, limit: 5, at: "19:00", next_day: false };

test("SIGNAL_WORDS: слова погоды — «перепад давления» и «перепад температуры»", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.pressure_drop, "перепад давления");
	assert.equal(SIGNAL_WORDS.temperature_rise, "перепад температуры");
	assert.equal(SIGNAL_WORDS.temperature_drop, "перепад температуры");
});

test("signalRows: pressure_drop — «перепад давления» и «7 к 19:00 (порог 5)»", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ ...WEATHER, kind: "pressure_drop" }]));
	assert.equal(row.word, "перепад давления");
	assert.equal(row.detail, "7 к 19:00 (порог 5)");
});

test("signalRows: pressure_drop 5.1 — «5.1 к 19:00 (порог 5)»", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ ...WEATHER, kind: "pressure_drop", value: 5.1 }]));
	assert.equal(row.detail, "5.1 к 19:00 (порог 5)");
});

test("signalRows: temperature_rise и temperature_drop — «перепад температуры», «8 к 15:00 (порог 7)»", async () => {
	const { signalRows } = await stateModel();
	for (const kind of ["temperature_rise", "temperature_drop"]) {
		const [row] = signalRows(stateOf([{ ...WEATHER, kind, value: 8.0, limit: 7, at: "15:00" }]));
		assert.equal(row.word, "перепад температуры");
		assert.equal(row.detail, "8 к 15:00 (порог 7)");
	}
});

test("signalRows: next_day true — «7 завтра к 03:00 (порог 5)»", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ ...WEATHER, kind: "pressure_drop", at: "03:00", next_day: true }]));
	assert.equal(row.detail, "7 завтра к 03:00 (порог 5)");
});

test("signalRows: next_day false — слова «завтра» нет", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ ...WEATHER, kind: "pressure_drop", at: "03:00" }]));
	assert.ok(!text(row).includes("завтра"));
});

test("signalRows: у температуры next_day true — «8 завтра к 06:00 (порог 7)»", async () => {
	const { signalRows } = await stateModel();
	const signal = { ...WEATHER, kind: "temperature_drop", value: 8.0, limit: 7, at: "06:00", next_day: true };
	const [row] = signalRows(stateOf([signal]));
	assert.equal(row.detail, "8 завтра к 06:00 (порог 7)");
});

test("signalRows: два сигнала погоды — порядок сервера, давление и температура", async () => {
	const { signalRows } = await stateModel();
	const rows = signalRows(
		stateOf([
			{ ...WEATHER, kind: "pressure_drop" },
			{ ...WEATHER, kind: "temperature_rise", value: 8.0, limit: 7, at: "15:00" },
		]),
	);
	assert.deepEqual(rows.map((row) => row.kind), ["pressure_drop", "temperature_rise"]);
});

test("signalRows: прежние коды без ключа at — деталь как до шага, без «к» и «завтра»", async () => {
	const { signalRows } = await stateModel();
	const rows = signalRows(
		stateOf([
			{ source: "illness", kind: "corridor_out", value: 1, limit: 2 },
			{ source: "deviations", kind: "wellbeing_below", value: 3, limit: 4 },
			{ source: "illness", kind: "illness_light", value: 2, limit: 5 },
		]),
	);
	assert.deepEqual(rows.map((row) => row.detail), ["1 (порог 2)", "3 (норма 4)", "день 2 из 5"]);
});

test("слова «ориентир» в модели нет", async () => {
	const { SIGNAL_WORDS, signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ ...WEATHER, kind: "pressure_drop" }]));
	assert.ok(!JSON.stringify([SIGNAL_WORDS, row]).includes("ориентир"));
});

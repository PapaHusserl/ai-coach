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
	"short_night", "sleep_debt", "illness_risk", "total_streak", "evening_streak", "weekend_work",
	"recovery_drop", "todo_growth", "who5_low", "who5_reduced", "who5_drop", "wellbeing", "mood",
	"stress", "symptoms", "readiness", "hrv", "sleep", "atl_over_ctl",
];

test("SIGNAL_WORDS: ровно 19 кодов отчётов", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.deepEqual(Object.keys(SIGNAL_WORDS).sort(), [...CODES].sort());
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

test("SIGNAL_WORDS: symptoms — «симптомы в тексте»", async () => {
	const { SIGNAL_WORDS } = await stateModel();
	assert.equal(SIGNAL_WORDS.symptoms, "симптомы в тексте");
});

test("detail: symptoms — слова через запятую, без порога", async () => {
	const symptoms = { source: "deviations", kind: "symptoms", value: ["горло", "насморк"], limit: null };
	const detail = await detailOf(symptoms);
	assert.equal(detail, "горло, насморк");
	assert.ok(!detail.includes("порог"));
});

test("signalRows: symptoms — слово строки «симптомы в тексте»", async () => {
	const { signalRows } = await stateModel();
	const [row] = signalRows(stateOf([{ source: "deviations", kind: "symptoms", value: ["горло"], limit: null }]));
	assert.equal(row.word, "симптомы в тексте");
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

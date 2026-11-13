// Пульт: вкладка «Состояние», чистые функции (тесты — tests/web/state.test.mjs).

// Слова сигналов отчётов (Р10 = 1); неизвестный код показывается как есть.
export const SIGNAL_WORDS = {
	short_night: "короткая ночь",
	sleep_debt: "долг сна",
	illness_risk: "возможно, заболеваешь",
	total_streak: "нагрузка три дня подряд",
	evening_streak: "работа по вечерам три дня",
	weekend_work: "работа в выходные",
	recovery_drop: "восстановление хуже",
	todo_growth: "туду растёт",
	who5_low: "WHO-5 низкий",
	who5_reduced: "WHO-5 снижен",
	who5_drop: "WHO-5 упал",
	wellbeing: "самочувствие",
	mood: "настроение",
	stress: "стресс",
	symptoms: "симптомы в тексте",
	readiness: "готовность",
	hrv: "HRV",
	sleep: "сон",
	atl_over_ctl: "ATL выше CTL",
};

const SERIES = [
	["sleep_h", "сон, ч"],
	["hrv", "HRV"],
	["rhr", "пульс покоя"],
	["readiness", "готовность"],
];

// Число или строка как есть, список — через запятую, словарь — «ключ значение» через запятую (Р23 = 1).
function shown(value) {
	if (Array.isArray(value)) return value.join(", ");
	if (value !== null && typeof value === "object") {
		return Object.entries(value).map(([key, item]) => `${key} ${item}`).join(", ");
	}
	return String(value);
}

// Строки сигналов в порядке сервера: [{kind, source, word, detail}].
export function signalRows(state) {
	return state.signals.map((signal) => ({
		kind: signal.kind,
		source: signal.source,
		word: SIGNAL_WORDS[signal.kind] ?? signal.kind,
		detail: signal.limit === null
			? shown(signal.value)
			: `${shown(signal.value)} (порог ${shown(signal.limit)})`,
	}));
}

// Пять рядов графиков: [{key, label, dates, values}]; у веса даты и числа — из записей.
export function trendSeries(state) {
	const { trends } = state;
	const weight = trends.weight;
	return [
		...SERIES.map(([key, label]) => ({ key, label, dates: trends.dates, values: trends[key] })),
		{ key: "weight", label: "вес, кг", dates: weight.map((row) => row.date), values: weight.map((row) => row.kg) },
	];
}

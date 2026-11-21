// Пульт: вкладка «Состояние», чистые функции (тесты — tests/web/state.test.mjs).

// Слова сигналов отчётов (Р10 = 1); неизвестный код показывается как есть.
export const SIGNAL_WORDS = {
	short_night: "короткая ночь",
	sleep_debt: "долг сна",
	illness_risk: "возможно, заболеваешь",
	corridor_out: "пульс или HRV вне нормы",
	hrv_streak: "статус HRV плохой подряд",
	illness_rest: "покой после болезни",
	illness_return: "возврат после болезни",
	illness_light: "лёгкий режим при COVID",
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
	fatigue: "усталость",
	irritability: "раздражительность",
	wellbeing_below: "самочувствие ниже нормы",
	mood_below: "настроение ниже нормы",
	symptoms: "симптомы",
	fever: "температура",
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

// У двух кодов «ниже нормы» limit — норма, не порог.
const NORM_KINDS = ["wellbeing_below", "mood_below"];

// Слова причин, по которым день покоя не засчитан (Н33, Р22 = а); неизвестный код — как есть.
export const REASON_WORDS = {
	no_record: "нет записи",
	no_night: "нет ночи с часов",
	corridor: SIGNAL_WORDS.corridor_out,
	skin_temp: "температура кожи выше нормы",
	respiration: "дыхание чаще нормы",
	spo2: "SpO2 ниже 92",
};

// Слова покоя и возврата у серии с отметкой COVID (Н49); лёгкий режим от отметки не зависит.
const COVID_WORDS = {
	illness_rest: "покой после COVID",
	illness_return: "возврат после COVID",
};

// Три кода фаз после болезни: «день N из M», у покоя — хвост причин.
const PHASE_KINDS = ["illness_rest", "illness_return", "illness_light"];

function wordOf(signal) {
	const word = (signal.covid && COVID_WORDS[signal.kind]) || SIGNAL_WORDS[signal.kind] || signal.kind;
	return signal.day ? `вчера вечером: ${word}` : word;
}

function detailOf(signal) {
	if (PHASE_KINDS.includes(signal.kind)) {
		const day = `день ${signal.count === "series" ? "болезни " : ""}${shown(signal.value)} из ${shown(signal.limit)}`;
		const why = signal.kind === "illness_rest" ? signal.why ?? [] : [];
		return why.length === 0 ? day : `${day} — ${why.map((code) => REASON_WORDS[code] ?? code).join(", ")}`;
	}
	if (signal.limit === null) return shown(signal.value);
	return `${shown(signal.value)} (${NORM_KINDS.includes(signal.kind) ? "норма" : "порог"} ${shown(signal.limit)})`;
}

// Строки сигналов в порядке сервера: [{kind, source, word, detail}].
export function signalRows(state) {
	return state.signals.map((signal) => ({
		kind: signal.kind,
		source: signal.source,
		word: wordOf(signal),
		detail: detailOf(signal),
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

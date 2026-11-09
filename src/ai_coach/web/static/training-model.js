// Пульт: модель окна тренировки — чистые функции, без DOM (тесты — tests/web/marks.test.mjs, через marks.js).

const STEP_WORDS = {
	warmup: "разминка",
	work: "работа",
	rest: "отдых",
	recovery: "восстановление",
	cooldown: "заминка",
};
const SECONDS_IN_MINUTE = 60;
const METERS_IN_KM = 1000;

function clock(seconds) {
	const total = Math.round(seconds);
	return `${Math.floor(total / SECONDS_IN_MINUTE)}:${String(total % SECONDS_IN_MINUTE).padStart(2, "0")}`;
}

function stepTime(seconds) {
	if (seconds < SECONDS_IN_MINUTE) return `${seconds} с`;
	const rest = seconds % SECONDS_IN_MINUTE;
	const minutes = Math.floor(seconds / SECONDS_IN_MINUTE);
	return rest === 0 ? `${minutes} мин` : `${minutes} мин ${rest} с`;
}

function stepLength(meters) {
	return meters < METERS_IN_KM ? `${meters} м` : `${meters / METERS_IN_KM} км`;
}

// Шаг плана {k, t, sec, m, reps, kg, pace} строкой: «разминка 5 мин», «Присед 12 × 20 кг»;
// title — название блока, если у шага своего нет.
export function stepText(step, title) {
	const own = step.k === "rest" ? undefined : title; // отдых между подходами не зовётся упражнением
	const parts = [step.t ?? own ?? STEP_WORDS[step.k] ?? step.k];
	if (step.sec != null) parts.push(stepTime(step.sec));
	if (step.m != null) parts.push(stepLength(step.m));
	if (step.reps != null && step.kg != null) parts.push(`${step.reps} × ${step.kg} кг`);
	else if (step.reps != null) parts.push(`${step.reps} повт.`);
	else if (step.kg != null) parts.push(`${step.kg} кг`);
	if (step.pace) parts.push(`${clock(Math.max(...step.pace))} - ${clock(Math.min(...step.pace))} /км`);
	return parts.join(" ");
}

// Строки таблицы шагов из блоков плана [{r, t, s: [шаг]}]; блок с повторами — «3 × …».
export function stepRows(blocks) {
	return blocks.flatMap((block) =>
		block.s.map((step) => (block.r > 1 ? `${block.r} × ` : "") + stepText(step, block.t)),
	);
}

// Доли зон Z1..Z5 факта в целых процентах; нулевые пропущены, зон нет — пусто.
export function zoneShares(fact) {
	if (!fact.zones) return [];
	return fact.zones
		.map((share, index) => ({ name: `Z${index + 1}`, percent: Math.round(share * 100) }))
		.filter((zone) => zone.percent > 0);
}

// Строки «План против факта» со знаком: ✓ у ok, ! у warn.
export function planFactRows(training) {
	const rows = training.fact?.rows ?? [];
	return rows.map((row) => ({ ...row, sign: row.mark === "ok" ? "✓" : "!" }));
}

function durationText(seconds) {
	const minutes = Math.round(seconds / SECONDS_IN_MINUTE);
	return minutes < SECONDS_IN_MINUTE
		? `${minutes} мин`
		: `${Math.floor(minutes / SECONDS_IN_MINUTE)} ч ${minutes % SECONDS_IN_MINUTE} мин`;
}

// Шесть чисел факта (прочерк, если Garmin их не дал); у факта без активности (пропуск) — пусто.
export function factNumbers(fact) {
	if (fact.duration_s == null && fact.distance_m == null) return [];
	const dash = "—";
	const value = (number, text) => (number == null ? dash : text(number));
	const distance = fact.distance_m || null; // 0 м — дистанции нет, как на сервере
	return [
		{ label: "Время", value: value(fact.duration_s, durationText) },
		{ label: "Дистанция", value: value(distance, (m) => `${(m / METERS_IN_KM).toFixed(1)} км`) },
		{ label: "Темп", value: value(fact.pace_s_km, (p) => `${clock(p)} /км`) },
		{ label: "Пульс ср.", value: value(fact.avg_hr, Math.round) },
		{ label: "Нагрузка", value: value(fact.training_load, Math.round) },
		{ label: "Ккал", value: value(fact.calories, Math.round) },
	];
}

// Плашка факта: слова и тон (good | warn | muted).
export function factPill(fact) {
	const pills = {
		done: { text: "✓ выполнено по плану", tone: "good" },
		different: { text: "выполнено иначе", tone: "warn" },
		skipped: { text: "пропущено", tone: "muted" },
	};
	return pills[fact.kind];
}

// Что не сделано у выполненной иначе силовой: «Не сделано: Присед, Тяга»; нечего показывать — "".
export function missingText(fact) {
	return fact.missing?.length ? `Не сделано: ${fact.missing.join(", ")}` : "";
}

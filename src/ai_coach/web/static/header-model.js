// Пульт: тексты строк шапки (чистые функции, тесты tests/web/header.test.mjs). Числа с точкой (Р15 = 1).

function number(value) {
	return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function has(value) {
	return value !== null && value !== undefined;
}

// «готовность 72 · сон 7.5 ч · HRV 48 · пульс 52»; пустые поля пропускаются.
export function metricsLine(metrics) {
	if (!metrics) return "показателей нет";
	const parts = [
		has(metrics.readiness) && `готовность ${number(metrics.readiness)}`,
		has(metrics.sleep_h) && `сон ${number(metrics.sleep_h)} ч`,
		has(metrics.hrv) && `HRV ${number(metrics.hrv)}`,
		has(metrics.rhr) && `пульс ${number(metrics.rhr)}`,
	];
	return parts.filter(Boolean).join(" · ") || "показателей нет";
}

// «вес 81.2 кг»; записи нет — «веса нет».
export function weightLine(weight) {
	return weight ? `вес ${number(weight.kg)} кг` : "веса нет";
}

// «синк 17:13» / «синк 17:13 ошибка» / «синк идёт…»; синков не было — «синка не было».
export function syncLine(sync, status) {
	if (status.running) return "синк идёт…";
	if (!sync.finished_at) return "синка не было";
	const time = sync.finished_at.slice(11, 16);
	return sync.status === "ok" && !sync.error ? `синк ${time}` : `синк ${time} ошибка`;
}

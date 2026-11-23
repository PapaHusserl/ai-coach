// Пульт: строки погоды под показателями, чистые функции. Слова — те же, что WORDS в weather.py
// (сверка: tests/test_weather_words.py).

const WORDS = {
	0: "ясно",
	1: "малооблачно",
	2: "переменная облачность",
	3: "пасмурно",
	45: "туман",
	48: "туман",
	51: "морось",
	53: "морось",
	55: "морось",
	56: "ледяная морось",
	57: "ледяная морось",
	61: "дождь",
	63: "дождь",
	65: "дождь",
	66: "ледяной дождь",
	67: "ледяной дождь",
	71: "снег",
	73: "снег",
	75: "снег",
	77: "снежная крупа",
	80: "ливень",
	81: "ливень",
	82: "ливень",
	85: "снегопад",
	86: "снегопад",
	95: "гроза",
	96: "гроза с градом",
	99: "гроза с градом",
};

const PLACE_WORDS = {
	denied: "нет доступа к геолокации",
	off: "нет доступа к геолокации",
	timeout: "место не определено",
	unavailable: "место не определено",
};

export function weatherWord(code) {
	return WORDS[code] ?? "";
}

// Целые градусы: «+4°», «0°», «−3°»; «−0» не бывает.
export function degrees(value) {
	const whole = Math.round(value) || 0;
	if (whole === 0) return "0°";
	return `${whole > 0 ? "+" : "−"}${Math.abs(whole)}°`;
}

function range(day) {
	return `${degrees(day.t_min).slice(0, -1)}…${degrees(day.t_max)}`;
}

function dayText(day) {
	const rain = typeof day.precip_prob === "number" ? `осадки ${day.precip_prob}%` : null;
	const parts = [range(day), weatherWord(day.code), rain];
	return parts.filter(Boolean).join(", ");
}

function nowLine(current) {
	const feels = degrees(current.apparent);
	const temperature = degrees(current.temperature);
	const head = feels === temperature ? `сейчас ${temperature}` : `сейчас ${temperature} (ощущается ${feels})`;
	return [head, weatherWord(current.code), `ветер ${Math.round(current.wind)} м/с`].filter(Boolean).join(" · ");
}

function missingLines(view) {
	if (view.missing === "range") return [];
	if (view.missing === "place") return [`погода: ${PLACE_WORDS[view.why] ?? PLACE_WORDS.unavailable}`];
	return ["погода: нет связи"];
}

function stamped(view, lines) {
	const stamp = `погода на ${view.fetched_at.slice(11, 16)}: `;
	return view.day ? [stamp + lines[0].replace("прогноз: ", "прогноз ")] : [stamp + lines[0], ...lines.slice(1)];
}

// Строки под показателями: view — ответ /api/weather; null — ответа ещё нет.
export function weatherLines(view) {
	if (!view) return ["погода: …"];
	if (view.missing) return missingLines(view);
	const lines = view.day
		? [`прогноз: ${dayText(view.day)}`]
		: [nowLine(view.current), `сегодня ${dayText(view.today)} · завтра ${dayText(view.tomorrow)}`];
	return view.stale ? stamped(view, lines) : lines;
}

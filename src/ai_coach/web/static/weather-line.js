// Пульт: строки погоды под показателями, только DOM (зовётся в браузере). Тексты — weather-model.js.
import { el } from "./dom.js";
import { weatherLines } from "./weather-model.js";

// Показывает «погода: …», затем строки по ответу /api/weather за день day; сбой запроса — «нет связи».
let asked = null; // день последнего запроса: опоздавший ответ другого дня не рисуется

export async function loadWeather(day) {
	const box = document.getElementById("weather");
	if (asked !== day) draw(box, null);
	asked = day;
	let view;
	try {
		const response = await fetch(`/api/weather?date=${day}`);
		if (!response.ok) throw new Error(String(response.status));
		view = await response.json();
	} catch {
		view = { missing: "silent" };
	}
	if (asked !== day) return;
	draw(box, view);
}

function draw(box, view) {
	box.replaceChildren(...weatherLines(view).map((text) => el("div", "", text)));
}

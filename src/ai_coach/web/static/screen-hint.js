// Пульт: строка «экран: …» над часами чек-ина, только DOM (зовётся в браузере). Тексты — marks-model.js.
import { el } from "./dom.js";
import { screenFill, screenHint } from "./marks-model.js";

// Узел строки за день day: читает /api/screen при создании; onFill({work, hobby}) — кнопка «подставить».
export function screenLine(day, onFill) {
	const line = el("div", "hline hint", "экран: …");
	load(line, day, onFill);
	return line;
}

async function load(line, day, onFill) {
	let view;
	try {
		const response = await fetch(`/api/screen?date=${day}`);
		if (!response.ok) throw new Error(String(response.status));
		view = await response.json();
	} catch {
		view = { missing: "silent" };
	}
	line.textContent = screenHint(view);
	if (view.missing) return;
	const fill = el("button", "link", "подставить");
	fill.type = "button";
	fill.addEventListener("click", () => onFill(screenFill(view)));
	line.append(fill);
}

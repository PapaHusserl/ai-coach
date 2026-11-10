// Пульт: вкладка «Тренировки», только DOM (зовётся в браузере). Чистые функции — week-model.js.
import { lineChart } from "./chart.js";
import { el } from "./dom.js";
import { weekRows, weekTitle } from "./week-model.js";

function renderWeek(week, today) {
	document.getElementById("week-title").textContent = weekTitle(week);
	const days = weekRows(week, today).map((row) => {
		const node = el("div", row.today ? "day today" : "day");
		node.append(el("b", "", row.label));
		for (const item of row.items) {
			node.append(el("span", "", item.title), el("span", `pill ${item.pill.tone}`, item.pill.text));
		}
		return node;
	});
	document.getElementById("week").replaceChildren(...days);
}

function renderLoad(load) {
	const chart = document.getElementById("load-chart");
	const note = document.getElementById("load-error");
	chart.replaceChildren();
	note.hidden = load.rows !== null;
	if (load.rows === null) {
		note.textContent = `нет данных: ${load.error}`;
		return;
	}
	const top = Math.ceil(Math.max(1, ...load.rows.map((row) => Math.max(row.ctl, row.atl))));
	lineChart(chart, load.rows, ["ctl", "atl"], { min: 0, max: top });
}

// Загрузить неделю дня day и нагрузку и показать на вкладке; при ошибке запроса — строка под нагрузкой.
export async function loadWeek(day, today) {
	const note = document.getElementById("load-error");
	try {
		const response = await fetch(`/api/week?date=${day}`);
		if (!response.ok) throw new Error(await response.text());
		const week = await response.json();
		renderWeek(week, today);
		renderLoad(week.load);
	} catch (error) {
		note.textContent = `Не удалось загрузить: ${error.message}`;
		note.hidden = false;
	}
}

// Пульт: вкладка «Состояние» — сигналы дня и пять графиков, только DOM (зовётся в браузере).
// Чистые функции — state-model.js, chart.js.
import { lineChart, valueRange } from "./chart.js";
import { el, svgNode } from "./dom.js";
import { signalRows, trendSeries } from "./state-model.js";

function node(id) {
	return document.getElementById(id);
}

function showNote(text) {
	const note = node("state-note");
	note.textContent = text;
	note.hidden = !text;
}

function trendNode(series) {
	const block = el("div", "trend");
	block.append(el("h3", "", series.label));
	const scale = valueRange(series.values);
	if (!scale) {
		block.append(el("p", "empty", "нет данных"));
		return block;
	}
	const svg = svgNode("svg", { class: "chart", viewBox: "0 0 320 140" });
	lineChart(svg, series.dates.map((date, index) => ({ date, value: series.values[index] })), ["value"], scale);
	block.append(svg);
	return block;
}

function renderState(state) {
	const rows = signalRows(state);
	node("state-empty").hidden = rows.length > 0;
	node("state-signals").replaceChildren(...rows.map((row) => {
		const item = el("li", "sig");
		item.append(el("b", "", row.word), el("span", "", ` · ${row.detail}`));
		return item;
	}));
	showNote(state.load_error === null ? "" : `нет данных: ${state.load_error}`);
	node("state-trends").replaceChildren(...trendSeries(state).map(trendNode));
}

// Загрузить состояние дня day и показать на вкладке; при ошибке запроса — строка под сигналами.
export async function loadState(day) {
	try {
		const response = await fetch(`/api/state?date=${day}`);
		if (!response.ok) throw new Error(await response.text());
		renderState(await response.json());
	} catch (error) {
		showNote(`Не удалось загрузить: ${error.message}`);
	}
}

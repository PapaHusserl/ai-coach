// Пульт: вкладка «Тренировки», только DOM (зовётся в браузере). Чистые функции — week-model.js.
import { chartPoints, weekRows, weekTitle } from "./week-model.js";

const SVG = "http://www.w3.org/2000/svg";
const WIDTH = 320;
const HEIGHT = 140;
const PAD = { left: 28, right: 10, top: 10, bottom: 20 };
const BOX = { x0: PAD.left, x1: WIDTH - PAD.right, y0: PAD.top, y1: HEIGHT - PAD.bottom };

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

function svgNode(tag, attrs, text) {
	const node = document.createElementNS(SVG, tag);
	for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
	if (text !== undefined) node.textContent = text;
	return node;
}

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

// Сетка и подписи оси: три горизонтали (min, середина, max), даты через одну.
function chartAxes(rows, box) {
	const nodes = [];
	const toY = (value) => chartPoints([value], box)[0][1];
	for (const value of [box.min, (box.min + box.max) / 2, box.max]) {
		const y = toY(value);
		nodes.push(svgNode("line", { x1: BOX.x0, x2: BOX.x1, y1: y, y2: y, stroke: "var(--line)" }));
		nodes.push(svgNode("text", { x: BOX.x0 - 4, y: y + 3, "text-anchor": "end" }, +value.toFixed(1)));
	}
	const xs = chartPoints(rows.map(() => 0), box).map((point) => point[0]);
	for (const [index, row] of rows.entries()) {
		if (index % 2 !== 0 && index !== rows.length - 1) continue;
		const label = String(Number(row.date.slice(8)));
		nodes.push(svgNode("text", { x: xs[index], y: HEIGHT - 5, "text-anchor": "middle" }, label));
	}
	return nodes;
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
	const ctl = load.rows.map((row) => row.ctl);
	const atl = load.rows.map((row) => row.atl);
	const box = { ...BOX, min: 0, max: Math.ceil(Math.max(1, ...ctl, ...atl)) };
	chart.append(...chartAxes(load.rows, box));
	for (const [name, series] of [["ctl", ctl], ["atl", atl]]) {
		const points = chartPoints(series, box);
		chart.append(svgNode("polyline", {
			class: name,
			points: points.map((point) => point.join(",")).join(" "),
			fill: "none",
			"stroke-width": 2,
		}));
		if (points.length) {
			const [cx, cy] = points.at(-1);
			chart.append(svgNode("circle", { class: name, cx, cy, r: 3.5 }));
		}
	}
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

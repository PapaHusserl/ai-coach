// Пульт: линейные графики вкладок «Тренировки» и «Состояние». Чистые chartPoints, chartSegments, valueRange;
// остальное — DOM (зовётся в браузере).
import { svgNode } from "./dom.js";

const WIDTH = 320;
const HEIGHT = 140;
const PAD = { left: 28, right: 10, top: 10, bottom: 20 };
const BOX = { x0: PAD.left, x1: WIDTH - PAD.right, y0: PAD.top, y1: HEIGHT - PAD.bottom };

// Точки графика [x, y] для ряда values в рамке box {x0, x1, y0, y1, min, max}: x равными шагами от x0 до x1,
// y0 — верх рамки (max), y1 — низ (min).
export function chartPoints(values, box) {
	const steps = Math.max(values.length - 1, 1);
	return values.map((value, index) => [
		box.x0 + (index * (box.x1 - box.x0)) / steps,
		box.y1 - ((value - box.min) / (box.max - box.min)) * (box.y1 - box.y0),
	]);
}

// Отрезки линии: null разрывает ряд, x — по индексу во всём ряду; пропуск в начале и в конце не рисуется.
export function chartSegments(values, box) {
	const points = chartPoints(values, box);
	const segments = [];
	let open = false;
	for (const [index, value] of values.entries()) {
		if (value === null) {
			open = false;
			continue;
		}
		if (!open) segments.push([]);
		segments.at(-1).push(points[index]);
		open = true;
	}
	return segments;
}

// Шкала Y по значениям без null: от минимума до максимума, ровный ряд — плюс-минус один; нет значений — null.
export function valueRange(values) {
	const found = values.filter((value) => value !== null);
	if (!found.length) return null;
	const [min, max] = [Math.min(...found), Math.max(...found)];
	return min === max ? { min: min - 1, max: max + 1 } : { min, max };
}

// Сетка и подписи оси: три горизонтали (min, середина, max), даты через одну.
function chartAxes(rows, box) {
	const nodes = [];
	const toY = (value) => chartPoints([value], box)[0][1];
	for (const value of [box.min, (box.min + box.max) / 2, box.max]) {
		const y = toY(value);
		nodes.push(svgNode("line", { x1: box.x0, x2: box.x1, y1: y, y2: y, stroke: "var(--line)" }));
		nodes.push(svgNode("text", { x: box.x0 - 4, y: y + 3, "text-anchor": "end" }, +value.toFixed(1)));
	}
	const xs = chartPoints(rows.map(() => 0), box).map((point) => point[0]);
	for (const [index, row] of rows.entries()) {
		if (index % 2 !== 0 && index !== rows.length - 1) continue;
		const label = String(Number(row.date.slice(8)));
		nodes.push(svgNode("text", { x: xs[index], y: HEIGHT - 5, "text-anchor": "middle" }, label));
	}
	return nodes;
}

// Оси и по линии на каждый ключ keys из rows [{date, <key>: число | null}]; scale {min, max}.
// Класс линии — ключ; одиночное значение между пропусками — малый кружок, последнее значение — кружок.
export function lineChart(svg, rows, keys, scale) {
	const box = { ...BOX, ...scale };
	svg.replaceChildren(...chartAxes(rows, box));
	for (const key of keys) {
		const values = rows.map((row) => row[key]);
		for (const points of chartSegments(values, box)) {
			if (points.length === 1) {
				const [cx, cy] = points[0];
				svg.append(svgNode("circle", { class: key, cx, cy, r: 2 }));
				continue;
			}
			svg.append(svgNode("polyline", {
				class: key,
				points: points.map((point) => point.join(",")).join(" "),
				fill: "none",
				"stroke-width": 2,
			}));
		}
		const last = chartSegments(values, box).at(-1)?.at(-1);
		if (last) svg.append(svgNode("circle", { class: key, cx: last[0], cy: last[1], r: 3.5 }));
	}
}

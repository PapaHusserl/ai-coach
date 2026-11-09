// Пульт: окно тренировки, только DOM (зовётся в браузере). Чистые функции — training-model.js.
import {
	factNumbers,
	factPill,
	missingText,
	planFactRows,
	stepRows,
	zoneShares,
} from "./training-model.js";

const NO_FACT_HINT = "Факт Garmin появится после coach sync; сделал без часов - жми „Сделал“.";
const ZONE_LABEL_FROM = 8; // подпись внутри полоски зоны — от стольких процентов

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

// Таблица окна: head — заголовки, rows — строки из ячеек; ячейка — текст или {text, tone}.
function table(head, rows) {
	const body = el("tbody");
	for (const cells of rows) {
		const tr = el("tr");
		for (const cell of cells) tr.append(el("td", cell.tone ?? "", cell.text ?? cell));
		body.append(tr);
	}
	const thead = el("thead");
	const headRow = el("tr");
	for (const title of head) headRow.append(el("th", "", title));
	thead.append(headRow);
	const wrap = el("div", "mtw");
	const node = el("table", "mt");
	node.append(thead, body);
	wrap.append(node);
	return wrap;
}

function zonesBar(fact) {
	const bar = el("div", "zones");
	for (const zone of zoneShares(fact)) {
		const label = `${zone.name} ${zone.percent}%`;
		const part = el("i", `z${zone.name.slice(1)}`, zone.percent >= ZONE_LABEL_FROM ? label : "");
		part.style.flex = String(zone.percent);
		part.title = label;
		bar.append(part);
	}
	return bar;
}

function numbersBlock(fact) {
	const numbers = el("div", "fk");
	for (const item of factNumbers(fact)) {
		const cell = el("div");
		cell.append(el("span", "", item.label), el("b", "", String(item.value)));
		numbers.append(cell);
	}
	return numbers;
}

// Факт Garmin: плашка, что не сделано, числа, «План против факта», зоны.
function factBlocks(training) {
	const fact = training.fact;
	const pill = factPill(fact);
	const head = el("div", "fh");
	head.append(el("span", `pill ${pill.tone}`, pill.text), el("span", "hint", fact.source));
	const blocks = [head];
	if (missingText(fact)) blocks.push(el("p", "hint", missingText(fact)));
	const numbers = numbersBlock(fact);
	if (numbers.children.length) blocks.push(numbers);
	const rows = planFactRows(training).map((r) => [
		r.label,
		r.plan,
		r.fact,
		{ text: r.sign, tone: r.mark === "ok" ? "good" : "warn" },
	]);
	if (rows.length) blocks.push(table(["План против факта", "План", "Факт", ""], rows));
	if (zoneShares(fact).length) {
		const zoneBox = el("div", "blk");
		zoneBox.append(el("span", "bar-label", "Время в пульсовых зонах"), zonesBar(fact));
		blocks.push(zoneBox);
	}
	return blocks;
}

// Окно тренировки сверху вкладки «Итог» в узле box: нет факта — шаги плана, есть — факт;
// у пропущенной шаги плана остаются; у прошедшей (past) без факта под шагами подсказка (Р25).
// Тренировка без плана в базе (нет training) сюда не попадает (Р15).
export function fillTraining(box, training, past) {
	box.replaceChildren();
	const { plan, fact } = training;
	if (fact) box.append(...factBlocks(training));
	if (fact && fact.kind !== "skipped") return;
	const steps = stepRows(plan.steps);
	if (steps.length) box.append(table(["Шаг"], steps.map((step) => [step])));
	if (!fact && past) box.append(el("p", "hint", NO_FACT_HINT));
}

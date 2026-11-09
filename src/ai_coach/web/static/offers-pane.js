// Пульт: варианты блюд в окне еды, только DOM (зовётся в браузере). Строки таблицы — marks-model.js.
import { offerRows } from "./marks-model.js";
import { table } from "./training-pane.js";

const HEAD = ["Что", "Сколько", "Ккал", "Б", "Ж", "У"];

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

// Блок вариантов: вкладки «Вариант N» (если их больше одного), таблица выбранного, «Съел вариант N».
// picked — номер выбранного варианта; onPick(index) — выбрать другой; onTake(offer) — съел (null — кнопки нет).
export function offersBlock(meal, picked, onPick, onTake) {
	const offers = meal.offers;
	const offer = offers[picked];
	const nodes = [];
	if (offers.length > 1) {
		const tabs = el("div", "mtabs");
		for (const [index] of offers.entries()) {
			const button = el("button", "", `Вариант ${index + 1}`);
			button.type = "button";
			button.setAttribute("aria-selected", String(index === picked));
			button.addEventListener("click", () => onPick(index));
			tabs.append(button);
		}
		nodes.push(tabs);
	}
	const { rows, foot } = offerRows(offer, meal.remaining);
	nodes.push(table(HEAD, rows, offer.name, foot));
	if (!onTake) return nodes; // у будущего пункта «Съел» нет
	const take = el("button", "save", offers.length > 1 ? `Съел вариант ${picked + 1}` : "Съел это");
	take.type = "button";
	take.addEventListener("click", () => onTake(offer));
	nodes.push(take);
	return nodes;
}

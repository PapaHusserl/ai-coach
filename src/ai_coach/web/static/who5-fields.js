// Пульт: поля формы WHO-5 (подписи шкалы и пять утверждений с кнопками 0–5), только DOM (зовётся в браузере).
// Тексты и правила — marks-model.js; значения живут в форме вкладки (q1–q5).
import { el } from "./dom.js";
import { WHO5_ITEMS, WHO5_LABELS, WHO5_NAMES, canSave } from "./marks-model.js";

// Узел полей: form — форма вкладки who5, save — кнопка «Сохранить».
export function who5Fields(form, save) {
	const box = el("div", "w5");
	const scale = WHO5_LABELS.map((label, value) => `${value} — ${label}`).join(" · ");
	box.append(el("p", "hint", `Как часто это было верно в последние две недели: ${scale}`));
	for (const [index, name] of WHO5_NAMES.entries()) {
		const line = el("div", "qs");
		const buttons = [];
		const mark = () => {
			for (const [value, other] of buttons.entries()) other.setAttribute("aria-pressed", String(value === form[name]));
		};
		for (let value = 0; value < WHO5_LABELS.length; value += 1) {
			const button = el("button", "", String(value));
			button.type = "button";
			button.title = WHO5_LABELS[value];
			button.addEventListener("click", () => {
				form[name] = value;
				mark();
				save.disabled = !canSave("who5", form);
			});
			buttons.push(button);
			line.append(button);
		}
		mark();
		const wrap = el("div", "w5row");
		wrap.append(el("span", "", `${index + 1}. ${WHO5_ITEMS[index]}`), line);
		box.append(wrap);
	}
	return box;
}

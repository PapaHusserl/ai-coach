// Пульт: поля формы отметки (шкалы, часы, погружение), только DOM (зовётся в браузере).
// Значения живут в форме вкладки; таблицы и чистые функции — marks-model.js.
import { FIELDS, FLOW_CHOICES, HOURS, REQUIRED, canSave } from "./marks-model.js";

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

// Шкала name вкладки tab; form — форма вкладки, save — кнопка «Сохранить».
export function scale(tab, form, name, save) {
	const field = FIELDS[name];
	const optional = !REQUIRED[tab].includes(name);
	// Строка: название, кнопки 1–5, полюса словами (Р8); у обязательной пустой шкалы название красное.
	const wrap = el("div", "sr");
	const line = el("div", "qs");
	const buttons = [];
	const mark = () => {
		wrap.classList.toggle("empty", !optional && !Number.isInteger(form[name]));
		for (const [index, other] of buttons.entries()) {
			other.setAttribute("aria-pressed", String(index + 1 === form[name]));
		}
	};
	for (let value = 1; value <= 5; value += 1) {
		const button = el("button", "", String(value));
		button.type = "button";
		button.addEventListener("click", () => {
			form[name] = optional && form[name] === value ? null : value;
			mark();
			save.disabled = !canSave(tab, form);
		});
		buttons.push(button);
		line.append(button);
	}
	wrap.append(el("span", "", field.label), line, el("span", "h", `${field.low} — ${field.high}`));
	mark();
	return wrap;
}

// Часы дня чек-ина: поля ввода, значение живёт в форме вкладки.
export function hoursFields(form) {
	const line = el("div", "hours");
	for (const [name, label] of Object.entries(HOURS)) {
		const wrap = el("label", "hour", label);
		const input = el("input");
		input.type = "number";
		input.min = "0";
		input.max = "24";
		input.step = "0.5";
		input.inputMode = "decimal";
		input.value = form[name] ?? "";
		input.addEventListener("input", () => {
			form[name] = input.value;
		});
		wrap.append(input);
		line.append(wrap);
	}
	return line;
}

// Погружение: да / нет, повторный клик снимает выбор.
export function flowField(form) {
	const wrap = el("div", "sr");
	const line = el("div", "yn");
	const buttons = [];
	for (const choice of FLOW_CHOICES) {
		const button = el("button", choice.flow === 1 ? "y" : "n", choice.label);
		button.type = "button";
		button.setAttribute("aria-pressed", String(form.flow === choice.flow));
		button.addEventListener("click", () => {
			form.flow = form.flow === choice.flow ? null : choice.flow;
			for (const [index, other] of buttons.entries()) {
				other.setAttribute("aria-pressed", String(FLOW_CHOICES[index].flow === form.flow));
			}
		});
		buttons.push(button);
		line.append(button);
	}
	wrap.append(el("span", "", "Погружение"), line);
	return wrap;
}

// Пульт: поля формы тренера под пунктом (число, шкала, да/нет, выбор из списка), только DOM
// (зовётся в браузере). Правила и строки — form-model.js; ответы живут в form.values вкладки.
import { el } from "./dom.js";
import { formCanSave } from "./form-model.js";
import { FIELDS } from "./marks-model.js";
import { scaleRow } from "./marks-fields.js";

const YES_NO = [
	{ label: "Да", value: true, cls: "y" },
	{ label: "Нет", value: false, cls: "n" },
];

// Ряд кнопок с выбором одного значения; повторный клик снимает выбор. Строка: подпись и ряд.
function choiceRow(field, form, choices, line, changed) {
	const values = form.values;
	const buttons = [];
	const mark = () => {
		for (const [index, button] of buttons.entries()) {
			button.setAttribute("aria-pressed", String(choices[index].value === values[field.key]));
		}
	};
	for (const choice of choices) {
		const button = el("button", choice.cls ?? "", choice.label);
		button.type = "button";
		button.addEventListener("click", () => {
			values[field.key] = values[field.key] === choice.value ? null : choice.value;
			mark();
			changed();
		});
		buttons.push(button);
		line.append(button);
	}
	mark();
	const wrap = el("div", "sr");
	wrap.append(el("span", "", field.label), line);
	return wrap;
}

// Строка числа: поле ввода и единица; значение — строка до отправки (запятая допустима).
function numberRow(field, form, changed) {
	const wrap = el("div", "sr");
	const line = el("div", "fnum");
	const input = el("input");
	input.type = "text";
	input.inputMode = "decimal";
	input.value = form.values[field.key] ?? "";
	input.addEventListener("input", () => {
		form.values[field.key] = input.value;
		changed();
	});
	line.append(input);
	if (field.unit) line.append(el("span", "h", field.unit));
	wrap.append(el("span", "", field.label), line);
	return wrap;
}

// Узел полей формы: fields — поля определения, form — черновик вкладки {values, text}, save — кнопка.
export function formFields(fields, form, save) {
	form.values ??= {};
	const box = el("div", "ff");
	const changed = () => {
		save.disabled = !formCanSave(fields, form.values);
	};
	for (const field of fields) {
		const optional = field.required === false;
		if (field.type === "number") box.append(numberRow(field, form, changed));
		else if (field.type === "yesno") box.append(choiceRow(field, form, YES_NO, el("div", "yn"), changed));
		else if (field.type === "choice") {
			const choices = field.options.map((option) => ({ label: option, value: option }));
			box.append(choiceRow(field, form, choices, el("div", "fch"), changed));
		} else {
			const poles = field.key === "score" ? { ...FIELDS.score, label: field.label } : field;
			box.append(scaleRow(poles, optional, form.values, field.key, changed));
		}
	}
	return box;
}

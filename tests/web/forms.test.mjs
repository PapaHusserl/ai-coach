import test from "node:test";
import assert from "node:assert/strict";
import { formCanSave, formLine, formPayload } from "../../src/ai_coach/web/static/form-model.js";

const SCORE = { key: "score", type: "scale", label: "Самочувствие" };
const TEMPERATURE = { key: "temperature", type: "number", label: "Температура", unit: "°C" };
const STOOL = { key: "stool", type: "choice", label: "Стул", options: ["норма", "жидкий"], required: false };
const FEVER = { key: "fever", type: "yesno", label: "Озноб", required: false };
const FIELDS = [SCORE, TEMPERATURE, STOOL];

test("formCanSave: без обязательного поля — нельзя", () => {
	assert.equal(formCanSave(FIELDS, { score: 4 }), false);
	assert.equal(formCanSave(FIELDS, { temperature: "37.2" }), false);
});

test("formCanSave: все обязательные заполнены — можно, необязательный пропущен", () => {
	assert.equal(formCanSave(FIELDS, { score: 4, temperature: "37.2" }), true);
});

test("formCanSave: число не числом — нельзя", () => {
	assert.equal(formCanSave(FIELDS, { score: 4, temperature: "abc" }), false);
	assert.equal(formCanSave(FIELDS, { score: 4, temperature: "" }), false);
});

test("formCanSave: ноль — число, можно", () => {
	assert.equal(formCanSave([TEMPERATURE], { temperature: "0" }), true);
	assert.equal(formCanSave([TEMPERATURE], { temperature: 0 }), true);
});

test("formCanSave: запятая как десятичный разделитель", () => {
	assert.equal(formCanSave([TEMPERATURE], { temperature: "37,2" }), true);
});

test("formCanSave: да/нет — ответ «нет» (false) засчитан как ответ", () => {
	const required = { ...FEVER, required: true };
	assert.equal(formCanSave([required], {}), false);
	assert.equal(formCanSave([required], { fever: false }), true);
});

test("formPayload: числа числами, запятая — точкой, свой event_id, date и mark form", () => {
	const form = { event_id: 5, date: "2026-11-08", values: { score: 4, temperature: "37,2" } };
	assert.deepEqual(formPayload(FIELDS, form), {
		event_id: 5,
		date: "2026-11-08",
		mark: "form",
		values: { score: 4, temperature: 37.2 },
	});
});

test("formPayload: пустые необязательные не уходят, текст обрезан", () => {
	const form = { event_id: 5, date: "2026-11-08", values: { score: 4, temperature: "37", stool: "" }, text: "  кашель " };
	const payload = formPayload(FIELDS, form);
	assert.deepEqual(payload.values, { score: 4, temperature: 37 });
	assert.equal(payload.text, "кашель");
});

test("formPayload: пустой текст не уходит", () => {
	const form = { event_id: 5, date: "2026-11-08", values: { score: 4, temperature: "37" }, text: "  " };
	assert.equal("text" in formPayload(FIELDS, form), false);
});

test("formPayload: выбор — текстом варианта, да/нет — булевым", () => {
	const form = { event_id: 5, date: "2026-11-08", values: { stool: "жидкий", fever: false } };
	assert.deepEqual(formPayload([STOOL, FEVER], form).values, { stool: "жидкий", fever: false });
});

test("formLine: оценка и число с единицей", () => {
	assert.equal(formLine(FIELDS, { score: 4, temperature: 37.2 }), "самочувствие 4 · 37.2 °C");
});

test("formLine: выбор — «подпись: вариант»", () => {
	const line = formLine(FIELDS, { score: 4, temperature: 37.2, stool: "жидкий" });
	assert.equal(line, "самочувствие 4 · 37.2 °C · стул: жидкий");
});

test("formCanSave: необязательное число — пусто можно, «abc» нельзя", () => {
	const optional = { ...TEMPERATURE, required: false };
	assert.equal(formCanSave([optional], { temperature: "" }), true);
	assert.equal(formCanSave([optional], {}), true);
	assert.equal(formCanSave([optional], { temperature: "abc" }), false);
});

test("formLine: ключ со значением null в строку не попадает", () => {
	assert.equal(formLine(FIELDS, { score: 4, temperature: null }), "самочувствие 4");
});

test("formLine: да/нет — «подпись: да» и «подпись: нет»", () => {
	assert.equal(formLine([FEVER], { fever: true }), "озноб: да");
	assert.equal(formLine([FEVER], { fever: false }), "озноб: нет");
});

test("formLine: число без единицы — «подпись N»", () => {
	const pulse = { key: "pulse", type: "number", label: "Пульс" };
	assert.equal(formLine([pulse], { pulse: 62 }), "пульс 62");
});

test("formLine: подпись с заглавными внутри — вся строчными", () => {
	const rpe = { key: "rpe", type: "scale", label: "RPE", low: "легко", high: "тяжело" };
	assert.equal(formLine([rpe], { rpe: 3 }), "rpe 3");
});

test("formLine: пропущенное необязательное поле в строку не попадает", () => {
	assert.equal(formLine(FIELDS, { temperature: 36.6 }), "36.6 °C");
});

function fakeNode(tag) {
	return {
		tag,
		textContent: "",
		children: [],
		classList: { toggle() {} },
		append(...nodes) {
			this.children.push(...nodes);
		},
		setAttribute() {},
		addEventListener() {},
	};
}

function texts(node) {
	return [node.textContent, ...node.children.flatMap(texts)];
}

test("score с подписью тренера: шкала — подпись тренера и полюса FIELDS.score, строка ответа — по подписи", async () => {
	globalThis.document = { createElement: fakeNode };
	try {
		const { formFields } = await import("../../src/ai_coach/web/static/form-fields.js");
		const { FIELDS: POLES } = await import("../../src/ai_coach/web/static/marks-model.js");
		const field = { key: "score", type: "scale", label: "Самочувствие утром" };
		const box = formFields([field], { values: {} }, { disabled: true });
		const all = texts(box);
		assert.ok(all.includes("Самочувствие утром"));
		assert.ok(!all.includes(POLES.score.label));
		assert.ok(all.includes(`${POLES.score.low} — ${POLES.score.high}`));
		assert.equal(formLine([field], { score: 4 }), "самочувствие утром 4");
	} finally {
		delete globalThis.document;
	}
});

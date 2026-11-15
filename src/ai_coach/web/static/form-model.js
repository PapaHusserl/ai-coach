// Пульт: модель формы тренера под пунктом — чистые функции, без DOM (тесты — tests/web/forms.test.mjs).
// Поле: {key, type: number | scale | yesno | choice, label, required?, unit?, options?}; ответы лежат
// вложенным объектом values (ключ поля может совпасть с text, date, event_id).

// Вкладки пункта без вкладки form, если определения формы у пункта нет (form:<имя> занесено в обход
// agenda/draft.py): красный пункт без вкладки, день рисуется.
export function withFormTab(tabs, form) {
	return form ? tabs : tabs.filter((tab) => tab !== "form");
}

const isRequired = (field) => field.required !== false;

// Число из поля ввода: "37,2" -> 37.2; пусто или не число -> null (как hoursValue в marks-model.js).
function numberValue(raw) {
	const text = String(raw ?? "").trim().replace(",", ".");
	const value = text === "" ? Number.NaN : Number(text);
	return Number.isFinite(value) ? value : null;
}

const isEmpty = (raw) => raw === undefined || raw === null || String(raw).trim() === "";

// Значение поля для отправки; нет ответа — undefined.
function answerOf(field, raw) {
	if (field.type === "number") return numberValue(raw) ?? undefined;
	if (field.type === "yesno") return typeof raw === "boolean" ? raw : undefined;
	if (isEmpty(raw)) return undefined;
	return field.type === "scale" ? Number(raw) : raw;
}

// Можно ли сохранять: обязательные поля отвечены, необязательное число — пусто или число.
export function formCanSave(fields, values) {
	return fields.every((field) => {
		const raw = values[field.key];
		if (answerOf(field, raw) !== undefined) return true;
		if (field.type === "number" && !isEmpty(raw)) return false;
		return !isRequired(field);
	});
}

// Тело POST /api/mark: форма {event_id, date, values, text}; пустые необязательные не уходят.
export function formPayload(fields, form) {
	const values = {};
	for (const field of fields) {
		const value = answerOf(field, (form.values ?? {})[field.key]);
		if (value !== undefined) values[field.key] = value;
	}
	const payload = { event_id: form.event_id, date: form.date, mark: "form", values };
	const text = (form.text ?? "").trim();
	if (text) payload.text = text;
	return payload;
}

function part(field, value) {
	const label = field.label.toLowerCase();
	if (field.type === "number") return field.unit ? `${value} ${field.unit}` : `${label} ${value}`;
	if (field.type === "yesno") return `${label}: ${value ? "да" : "нет"}`;
	if (field.type === "choice") return `${label}: ${value}`;
	return `${label} ${value}`;
}

// Строка ответа: «самочувствие 4 · 37.2 °C · стул: жидкий»; пропущенные поля не выводятся.
export function formLine(fields, answers) {
	return fields
		.filter((field) => answers[field.key] !== undefined && answers[field.key] !== null)
		.map((field) => part(field, answers[field.key]))
		.join(" · ");
}

// Строка записи формы из marks.forms {values, score, text, logged_at}: оценка самочувствия, если есть, —
// среди значений (ключ score).
function entryLine(form, entry) {
	return formLine(form.fields, { ...entry.values, ...(entry.score == null ? {} : { score: entry.score }) });
}

// Строка последнего ответа формы пункта для сводки; нет формы или ответа — "".
export function lastFormLine(marks, form) {
	const last = marks.forms?.at(-1);
	return form && last ? entryLine(form, last) : "";
}

// Строки истории по ответам формы: {at, tab: "form", text}; без значений — название формы.
export function formRows(marks, form, withText) {
	return (marks.forms ?? []).map((entry) => {
		const head = (form && entryLine(form, entry)) || form?.title || "Форма";
		return { at: entry.logged_at, tab: "form", text: withText(head, entry.text) };
	});
}

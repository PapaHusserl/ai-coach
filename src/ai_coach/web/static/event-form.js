// Пульт: форма нового пункта плана (шкала и перенос туду), только DOM (зовётся в браузере).
// Чистые функции — scale-model.js.
import { el } from "./dom.js";
import { CATEGORIES, KINDS, createPayload } from "./scale-model.js";

const clock = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;

export async function postEvent(payload) {
	try {
		const response = await fetch("/api/event", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		});
		// 200 с error — «записан черновиком»: пункт создан, но текст сбоя Календаря показываем.
		if (response.ok) return { ok: true, text: (await response.json()).error ?? "" };
		const text = (await response.text()).trim();
		const known = response.status === 400 || response.status === 404;
		return { ok: false, text: known ? text : `Не сохранилось, ошибка пульта (код ${response.status})` };
	} catch (error) {
		console.error("POST /api/event не удался", error);
		return { ok: false, text: "Не сохранилось, нет связи с пультом" };
	}
}

function timeInput(min) {
	const input = el("input");
	input.type = "time";
	input.value = clock(min);
	return input;
}

// Минуты суток из "HH:MM"; конец 00:00 — полночь следующего дня.
const minutesOf = (value) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));

export function closeEventForm(box) {
	box.replaceChildren();
	box.hidden = true;
}

// Форма в box. day — "YYYY-MM-DD", span — {start, end} в минутах, title — начальное название,
// fixedKind — вид без выбора (ряд видов скрыт), fail(text) — показать ошибку,
// onDone() — после «Создать» (успех) и «Отмена»; форму закрывает сама.
export function openEventForm(box, { day, span, title = "", fixedKind = null, fail, onDone }) {
	const choice = { kind: fixedKind ?? "task", category: "work" };
	const kinds = el("div", "chips");
	const categories = el("div", "chips");
	const name = el("input");
	name.value = title;
	// Ряд кнопок одного выбора: нажатая помечена aria-pressed.
	const choices = (row, items, key, after) => {
		const buttons = items.map(([value, label]) => {
			const button = el("button", "", label);
			button.addEventListener("click", () => {
				choice[key] = value;
				for (const [other, mark] of buttons) mark.setAttribute("aria-pressed", String(other === value));
				after();
			});
			return [value, button];
		});
		for (const [value, button] of buttons) button.setAttribute("aria-pressed", String(value === choice[key]));
		row.replaceChildren(...buttons.map(([, button]) => button));
	};
	const refresh = () => {
		categories.hidden = choice.kind !== "task";
		name.placeholder = KINDS.find((item) => item.value === choice.kind).word;
	};
	choices(kinds, KINDS.map((item) => [item.value, item.label]), "kind", refresh);
	choices(categories, CATEGORIES.map((item) => [item, item]), "category", refresh);
	kinds.hidden = fixedKind !== null;
	refresh();
	const start = timeInput(span.start);
	const end = timeInput(span.end);
	const save = el("button", "", "Создать");
	const cancel = el("button", "", "Отмена");
	save.addEventListener("click", async () => {
		if (!start.value || !end.value) {
			fail("Укажи время начала и конца.");
			return;
		}
		const from = minutesOf(start.value);
		const to = minutesOf(end.value) || 1440;
		const midnight = `${day}T00:00:00`;
		const at = (m) => new Date(Date.parse(`${midnight}Z`) + m * 60000).toISOString().slice(0, 19);
		save.disabled = true; // второе нажатие создало бы второе событие
		const reply = await postEvent(createPayload({ ...choice, title: name.value, start_at: at(from), end_at: at(to) }));
		fail(reply.text);
		save.disabled = false;
		if (!reply.ok) return;
		closeEventForm(box);
		onDone();
	});
	cancel.addEventListener("click", () => {
		fail("");
		closeEventForm(box);
		onDone();
	});
	name.className = "wide";
	const times = el("div", "frow");
	times.append("с ", start, " до ", end);
	const actions = el("div", "frow");
	actions.append(save, cancel);
	box.replaceChildren(kinds, categories, name, times, actions);
	box.hidden = false;
	name.focus();
}

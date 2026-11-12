// Пульт: окно чужой встречи под строкой, только DOM (зовётся в браузере). Правка одного вхождения (Р8 = 1),
// время у события на весь день заперто (Р18 = 1), встреча с участниками и календарь без записи — просмотр (Р9, Р15).
import { el } from "./dom.js";
import { dayOf, newTimes } from "./meeting-model.js";
import { formatClock } from "./pult-model.js";
import { postJson } from "./post.js";
import { toast } from "./toast.js";

let busy = false;
let shown = null; // узел открытого окна: пока он на странице, таймер пульта окно не перерисовывает

// Занято: идёт запись или окно встречи открыто (набранное не сбрасывается).
export const meetingBusy = () => busy || (shown !== null && shown.isConnected);

function field(label, input) {
	input.setAttribute("aria-label", label);
	return input;
}

function input(type, value) {
	const node = el("input");
	node.type = type;
	node.value = value;
	return node;
}

// item — li строки, row — строка встречи, ctx — {reload, close}: перечитать день и свернуть окно.
export function mountMeeting(item, row, ctx) {
	const box = el("div", "mform");
	const error = el("p", "error");
	error.hidden = true;
	const fail = (text) => {
		error.textContent = text;
		error.hidden = text === "";
	};
	box.append(el("p", "hint", "Загружаю…"), error);
	item.append(box);
	shown = box;
	load(box, row, ctx, fail);
}

async function load(box, row, ctx, fail) {
	let view;
	try {
		const response = await fetch(`/api/meeting?id=${row.id}`);
		if (!response.ok) throw new Error((await response.text()).trim());
		view = await response.json();
	} catch (error) {
		box.firstChild.remove();
		fail(`Не удалось загрузить: ${error.message}`);
		return;
	}
	const locked = !view.editable;
	const title = field("Название", input("text", view.title ?? ""));
	title.className = "wide";
	const note = field("Описание", el("textarea", "wide"));
	note.value = view.note ?? "";
	note.rows = 3;
	const date = field("Дата", input("date", dayOf(view.start_at)));
	const from = field("С", input("time", formatClock(view.start_at)));
	const to = field("До", input("time", formatClock(view.end_at)));
	for (const node of [title, note, date, from, to]) node.disabled = locked;
	from.disabled = locked || view.all_day; // время события на весь день заперто (Р18 = 1)
	to.disabled = locked || view.all_day;
	const times = el("div", "frow");
	times.append("дата ", date, view.all_day ? " весь день" : " с ", ...(view.all_day ? [] : [from, " до ", to]));
	const head = el("p", "hint", [view.calendar, view.recurring && "повторяется — меняется только этот день"].filter(Boolean).join(" · "));
	box.replaceChildren(head, title, note, times);
	if (locked) {
		box.append(el("p", "hint", view.reason ?? ""), error);
		return;
	}
	const save = el("button", "", "Сохранить");
	const remove = el("button", "", "Удалить");
	const sure = el("button", "", "точно удалить");
	const cancel = el("button", "", "отмена");
	sure.hidden = true;
	cancel.hidden = true;
	const send = async (payload, done) => {
		busy = true;
		fail("");
		const result = await postJson("/api/meeting", { id: row.id, ...payload });
		busy = false;
		if (!result.ok) {
			fail(result.text);
			return;
		}
		toast("Записано");
		done();
	};
	save.addEventListener("click", () => {
		if (!date.value || (!view.all_day && (!from.value || !to.value))) {
			fail("Укажи дату и время.");
			return;
		}
		const values = {};
		if (title.value !== (view.title ?? "")) values.title = title.value;
		if (note.value !== (view.note ?? "")) values.note = note.value;
		const times = newTimes(view, date.value, from.value, to.value);
		if (times.start_at !== view.start_at || times.end_at !== view.end_at) Object.assign(values, times);
		if (Object.keys(values).length === 0) return;
		send({ action: "update", ...values }, ctx.reload);
	});
	remove.addEventListener("click", () => {
		remove.hidden = true;
		sure.hidden = false;
		cancel.hidden = false;
	});
	cancel.addEventListener("click", () => {
		remove.hidden = false;
		sure.hidden = true;
		cancel.hidden = true;
	});
	sure.addEventListener("click", () =>
		send({ action: "remove" }, () => {
			ctx.close();
			ctx.reload();
		}),
	);
	const actions = el("div", "frow");
	actions.append(save, remove, sure, cancel);
	box.append(actions, error);
}

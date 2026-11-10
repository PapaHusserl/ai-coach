// Пульт: шкала дня под баром, только DOM (зовётся в браузере). Чистые функции — scale-model.js.
// Блок тренера тянется (сдвиг), правый край — длительность, клик в пустоту — форма нового пункта.
import { el } from "./dom.js";
import { formatClock } from "./pult-model.js";
import {
	CATEGORIES,
	KINDS,
	blockBox,
	createPayload,
	dragOutcome,
	frameOf,
	locked,
	minuteAt,
	newSpan,
	snap,
} from "./scale-model.js";

const DRAG_PX = 4; // меньше — это клик, не перетаскивание
const EDGE_PX = 12; // правый край блока — длительность

const ui = {};
// pressed — кнопка нажата, active — тянем, saving — ждём ответ сервера, quiet — миг после жеста (клик не наш).
const drag = { pressed: false, active: false, saving: false, quiet: false };
let shownDay = null;
let formOpen = false;

const dragging = () => drag.pressed || drag.active || drag.saving;

// Пока блок тянут или открыта форма, таймер пульта шкалу и страницу не перерисовывает.
export const scaleBusy = () => dragging() || formOpen;

const clock = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;

function fail(text) {
	ui.error.textContent = text;
	ui.error.hidden = text === "";
}

async function post(payload) {
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

function place(node, box) {
	node.style.left = `${box.left}%`;
	node.style.width = `${box.width}%`;
}

function startDrag(event, node, row, ctx) {
	if (dragging()) return;
	const rect = node.getBoundingClientRect();
	const edge = rect.right - event.clientX <= Math.min(EDGE_PX, rect.width / 3);
	const mode = edge ? "resize" : "move";
	const from = event.clientX;
	const width = ui.track.getBoundingClientRect().width;
	let outcome = null;
	let delta = 0;
	drag.pressed = true;
	node.setPointerCapture(event.pointerId);
	const release = () => {
		node.removeEventListener("pointermove", onMove);
		node.removeEventListener("pointerup", onUp);
		node.removeEventListener("pointercancel", onCancel);
		ui.tip.hidden = true;
		drag.pressed = false;
		// После любого отпускания на блоке браузер шлёт click (и без сдвига) — в пустоту он не засчитывается.
		drag.quiet = true;
		setTimeout(() => {
			drag.quiet = false;
		}, 0);
	};
	function onMove(move) {
		const dx = move.clientX - from;
		if (!drag.active && Math.abs(dx) < DRAG_PX) return;
		drag.active = true;
		delta = snap(((ctx.frame.end - ctx.frame.start) * dx) / width, 5);
		outcome = dragOutcome(mode, row, delta);
		const box = blockBox(outcome, ctx.frame);
		place(node, box);
		ui.tip.style.left = `${Math.min(Math.max(box.left, 0), 80)}%`;
		ui.tip.textContent = `${formatClock(outcome.start_at)}–${formatClock(outcome.end_at)}`;
		ui.tip.hidden = false;
	}
	// Жест отменён системой: ничего не пишем, блок на место.
	function onCancel() {
		release();
		drag.active = false;
		place(node, blockBox(row, ctx.frame));
	}
	async function onUp() {
		release();
		if (!drag.active) return;
		drag.active = false;
		if (delta === 0) return;
		drag.saving = true;
		const payload = mode === "move"
			? { action: "move", id: row.id, start_at: outcome.start_at }
			: { action: "resize", id: row.id, end_at: outcome.end_at };
		fail((await post(payload)).text);
		drag.saving = false;
		ctx.reload();
	}
	node.addEventListener("pointermove", onMove);
	node.addEventListener("pointerup", onUp);
	node.addEventListener("pointercancel", onCancel);
}

function blockNode(row, ctx) {
	const node = el("div", `blk-ev${row.source === "meeting" ? " meet" : ""}${locked(row) ? " lock" : ""}`);
	node.title = `${formatClock(row.start_at)} ${row.title || "Встреча"}`;
	node.append(el("span", "", row.title || "Встреча"));
	place(node, blockBox(row, ctx.frame));
	if (!locked(row)) {
		node.append(el("i", "handle"));
		node.addEventListener("pointerdown", (event) => {
			if (event.button !== 0 || !event.isPrimary) return;
			event.stopPropagation();
			startDrag(event, node, row, ctx);
		});
	}
	return node;
}

function timeInput(min) {
	const input = el("input");
	input.type = "time";
	input.value = clock(min);
	return input;
}

// Минуты суток из "HH:MM"; конец 00:00 — полночь следующего дня.
const minutesOf = (value) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));

function closeForm() {
	formOpen = false;
	ui.form.replaceChildren();
	ui.form.hidden = true;
}

function openForm(min, ctx) {
	const span = newSpan(min, ctx.frame);
	const choice = { kind: "task", category: "work" };
	const kinds = el("div", "chips");
	const categories = el("div", "chips");
	const title = el("input");
	// Ряд кнопок одного выбора: нажатая помечена aria-pressed.
	const choices = (box, items, key, after) => {
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
		box.replaceChildren(...buttons.map(([, button]) => button));
	};
	const refresh = () => {
		categories.hidden = choice.kind !== "task";
		title.placeholder = KINDS.find((item) => item.value === choice.kind).word;
	};
	choices(kinds, KINDS.map((item) => [item.value, item.label]), "kind", refresh);
	choices(categories, CATEGORIES.map((name) => [name, name]), "category", refresh);
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
		const midnight = `${ctx.day}T00:00:00`;
		const at = (m) => new Date(Date.parse(`${midnight}Z`) + m * 60000).toISOString().slice(0, 19);
		save.disabled = true; // второе нажатие создало бы второе событие
		const reply = await post(createPayload({ ...choice, title: title.value, start_at: at(from), end_at: at(to) }));
		fail(reply.text);
		save.disabled = false;
		if (!reply.ok) return;
		closeForm();
		ctx.reload();
	});
	cancel.addEventListener("click", () => {
		fail("");
		closeForm();
		ctx.reload();
	});
	formOpen = true;
	ui.form.replaceChildren(kinds, categories, title, start, end, save, cancel);
	ui.form.hidden = false;
	title.focus();
}

function ticks(frame) {
	const length = frame.end - frame.start;
	const nodes = [];
	for (let hour = Math.ceil(frame.start / 60); hour * 60 <= frame.end; hour += 1) {
		const tick = el("span", "tick", String(hour));
		tick.style.left = `${(100 * (hour * 60 - frame.start)) / length}%`;
		nodes.push(tick);
	}
	return nodes;
}

function mount(box) {
	ui.track = el("div", "scale");
	ui.tip = el("div", "tip");
	ui.tip.hidden = true;
	ui.form = el("div", "chips");
	ui.form.hidden = true;
	ui.error = el("p", "error");
	ui.error.hidden = true;
	box.append(ui.track, ui.form, ui.error);
}

// view — ответ /api/day; reload — перечитать день после правки.
export function renderScale(view, reload) {
	const box = document.getElementById("scale");
	if (!ui.track) mount(box);
	if (dragging() && shownDay === view.date) return; // открытая форма перерисовке не мешает
	if (shownDay !== view.date) {
		// Жест прежнего дня не доживёт до своего pointerup: сбрасываем, иначе шкала мёртвая.
		drag.pressed = false;
		drag.active = false;
		ui.tip.hidden = true;
		closeForm();
		fail("");
	}
	shownDay = view.date;
	const ctx = { frame: frameOf(view), day: view.date, reload };
	const rows = [
		...view.items.map((row) => ({ ...row, source: "item" })),
		...view.meetings.map((row) => ({ ...row, source: "meeting" })),
	].filter((row) => !row.all_day);
	ui.track.replaceChildren(...ticks(ctx.frame), ...rows.map((row) => blockNode(row, ctx)), ui.tip);
	// Клик в пустоту: клик по блоку (его подписи и ручке) и клик, завершающий перетаскивание, не считаются.
	ui.track.onclick = (event) => {
		if (drag.quiet || dragging() || event.target !== ui.track) return;
		const rect = ui.track.getBoundingClientRect();
		openForm(minuteAt(event.clientX - rect.left, rect.width, ctx.frame), ctx);
	};
}

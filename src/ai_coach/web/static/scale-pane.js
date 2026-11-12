// Пульт: шкала дня под баром, только DOM (зовётся в браузере). Чистые функции — scale-model.js.
// Блок тренера тянется (сдвиг), правый край — длительность, клик в пустоту — форма нового пункта.
import { el } from "./dom.js";
import { openEventForm, postEvent } from "./event-form.js";
import { formatClock } from "./pult-model.js";
import {
	blockBox,
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

function fail(text) {
	ui.error.textContent = text;
	ui.error.hidden = text === "";
}

function place(node, box) {
	node.style.left = `${box.left}%`;
	node.style.width = `${box.width}%`;
}

// Подсказка над полосой: «09:35–10:20 Название» над блоком с рамкой box.
function showTip(row, box) {
	ui.tip.style.left = `${Math.min(Math.max(box.left, 0), 80)}%`;
	ui.tip.textContent = `${formatClock(row.start_at)}–${formatClock(row.end_at)} ${row.title || "Встреча"}`;
	ui.tip.hidden = false;
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
		showTip({ ...row, ...outcome }, box);
	}
	// Жест отменён системой: ничего не пишем, блок на место.
	function onCancel() {
		release();
		drag.active = false;
		place(node, blockBox(row, ctx.frame));
	}
	async function onUp() {
		release();
		if (!drag.active) {
			ctx.open(row.id); // нажали и отпустили без сдвига — это клик по блоку
			return;
		}
		drag.active = false;
		if (delta === 0) return;
		drag.saving = true;
		const payload = mode === "move"
			? { action: "move", id: row.id, start_at: outcome.start_at }
			: { action: "resize", id: row.id, end_at: outcome.end_at };
		fail((await postEvent(payload)).text);
		drag.saving = false;
		ctx.reload();
	}
	node.addEventListener("pointermove", onMove);
	node.addEventListener("pointerup", onUp);
	node.addEventListener("pointercancel", onCancel);
}

function blockNode(row, ctx) {
	const node = el("div", `blk-ev${row.source === "meeting" ? " meet" : ""}${locked(row) ? " lock" : ""}`);
	node.append(el("span", "", row.title || "Встреча"));
	place(node, blockBox(row, ctx.frame));
	// Подсказка: мышь наводит, палец нажимает; пока тянут, её ведёт перетаскивание.
	const show = () => showTip(row, blockBox(row, ctx.frame));
	const hide = () => {
		if (!dragging()) ui.tip.hidden = true;
	};
	node.addEventListener("pointerenter", () => {
		if (!dragging()) show();
	});
	node.addEventListener("pointerleave", hide);
	node.addEventListener("pointerup", hide);
	node.addEventListener("pointercancel", hide);
	if (!locked(row)) {
		node.append(el("i", "handle"));
		node.addEventListener("pointerdown", (event) => {
			if (event.button !== 0 || !event.isPrimary) return;
			event.stopPropagation();
			show();
			startDrag(event, node, row, ctx);
		});
	} else {
		node.addEventListener("pointerdown", show);
		// Повтор не двигается, но раскрывается; встреча — нет.
		if (row.source === "item") node.addEventListener("click", () => ctx.open(row.id));
	}
	return node;
}

function closeForm() {
	formOpen = false;
	ui.form.replaceChildren();
	ui.form.hidden = true;
}

function openForm(min, ctx) {
	formOpen = true;
	openEventForm(ui.form, {
		day: ctx.day,
		span: newSpan(min, ctx.frame),
		fail,
		onDone: () => {
			formOpen = false;
			ctx.reload();
		},
	});
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
	ui.form = el("div", "sform");
	ui.form.hidden = true;
	ui.error = el("p", "error");
	ui.error.hidden = true;
	box.append(ui.track, ui.form, ui.error);
}

// view — ответ /api/day; reload — перечитать день после правки; open(id) — раскрыть пункт в списке.
export function renderScale(view, reload, open) {
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
	const ctx = { frame: frameOf(view), day: view.date, reload, open };
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

// Пульт: план дня, DOM (в браузере). Чистые функции — pult-model.js, здесь реэкспорт для тестов (tests/web).

import { isPast, mountMarks, setupMarks, unmountMarks } from "./marks.js";
import {
	barLabel,
	barPercent,
	dayRows,
	formatClock,
	formatDate,
	hasWindow,
	itemProgress,
	nextRow,
	openedId,
	part,
	rowStatus,
	shiftDay,
} from "./pult-model.js";

import { loadWeek } from "./week-pane.js";

export * from "./pult-model.js";
export * from "./week-model.js";

const REFRESH_MS = 60000;

function rowText(row) {
	const time = row.all_day ? "весь день" : formatClock(row.start_at);
	const draft = row.status === "draft" ? " (черновик)" : "";
	return [time, `${row.title || "Встреча"}${draft}`];
}

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

function progressNode(progress) {
	const box = el("div", "prog");
	const bar = el("div", "bar");
	const fill = el("i");
	fill.style.width = `${progress.percent}%`;
	const marker = el("b");
	marker.style.left = `${progress.percent}%`;
	bar.append(fill, marker);
	const label = el("div", "pl");
	label.append(
		el("span", "", `прошло ${part(progress.elapsedMin)}`),
		el("span", "", `${progress.percent}%`),
		el("span", "", `осталось ${part(progress.leftMin)} · до ${progress.until}`),
	);
	box.append(bar, label);
	return box;
}

// Строка раскрывает окно кликом и с клавиатуры (Enter, пробел).
function makeTappable(head, toggle, expanded) {
	head.tabIndex = 0;
	head.setAttribute("role", "button");
	head.setAttribute("aria-expanded", String(expanded));
	head.addEventListener("click", toggle);
	head.addEventListener("keydown", (event) => {
		if (event.key !== "Enter" && event.key !== " ") return;
		event.preventDefault();
		toggle();
	});
}

function rowClasses(row, now, open) {
	const flags = {
		allday: row.all_day,
		muted: row.muted,
		past: isPast(row, now),
		current: row.current,
		due: row.due,
		tap: hasWindow(row),
		open,
	};
	return ["agi", ...Object.keys(flags).filter((name) => flags[name])].join(" ");
}

// choice — что раскрыл пользователь (см. openedId); lastView — по нему перерисовка без запроса.
let choice = null;
let lastView = null;

function rowNode(row, view, next, openId) {
	const open = hasWindow(row) && row.id === openId;
	const item = el("li", rowClasses(row, view.now, open));
	const [time, title] = rowText(row);
	const head = el("div", "agh");
	const status = rowStatus(row, view.now, row === next);
	head.append(el("span", "tm", time), el("span", "ttl", title), el("span", `st ${status.tone}`.trim(), status.text));
	if (hasWindow(row)) {
		makeTappable(head, () => {
			choice = open ? false : row.id;
			render(lastView);
		}, open);
	}
	item.append(head);
	const progress = row.current ? itemProgress(row, view.now) : null;
	if (progress) item.append(progressNode(progress));
	if (open) mountMarks(item, row, view);
	return item;
}

function render(view) {
	lastView = view;
	document.getElementById("date").textContent = formatDate(view.date);
	document.getElementById("now").textContent = formatClock(view.now);
	document.getElementById("fill").style.width = `${barPercent(view.elapsed_min, view.left_min)}%`;
	document.getElementById("bar-label").textContent = barLabel(view.elapsed_min, view.left_min);
	const rows = dayRows(view);
	document.getElementById("empty").hidden = rows.length > 0;
	const next = nextRow(rows, view);
	const openId = openedId(choice, rows);
	if (openId === null) unmountMarks();
	document.getElementById("rows").replaceChildren(...rows.map((row) => rowNode(row, view, next, openId)));
}

// Таймер не перерисовывает список, пока в окне пункта идёт ввод (прототип :513).
function typing() {
	const active = document.activeElement;
	return Boolean(active?.closest(".pane")) && ["INPUT", "TEXTAREA"].includes(active.tagName);
}

if (typeof document !== "undefined") {
	let day = null;
	const load = async () => {
		const query = day ? `?date=${day}` : "";
		const message = document.getElementById("error");
		try {
			const response = await fetch(`/api/day${query}`);
			if (!response.ok) throw new Error(await response.text());
			const view = await response.json();
			message.hidden = true;
			render(view);
			document.body.dataset.day = view.date;
			document.body.dataset.today = view.now.slice(0, 10);
			if (!document.querySelector('[data-panel="train"]').hidden) loadWeek(view.date, view.now.slice(0, 10));
		} catch (error) {
			message.textContent = `Не удалось загрузить: ${error.message}`;
			message.hidden = false;
		}
	};
	const move = (delta) => {
		const shown = document.body.dataset.day ?? day;
		if (!shown) return;
		day = shiftDay(shown, delta);
		choice = null;
		load();
	};
	setupMarks(load);
	const tabs = document.querySelectorAll("#tabs button");
	for (const tab of tabs) {
		tab.addEventListener("click", () => {
			for (const other of tabs) other.setAttribute("aria-selected", String(other === tab));
			for (const panel of document.querySelectorAll("[data-panel]")) {
				panel.hidden = panel.dataset.panel !== tab.dataset.tab;
			}
			if (tab.dataset.tab === "train" && document.body.dataset.day) {
				loadWeek(document.body.dataset.day, document.body.dataset.today);
			}
		});
	}
	document.getElementById("prev").addEventListener("click", () => move(-1));
	document.getElementById("next").addEventListener("click", () => move(1));
	load();
	setInterval(() => {
		if (!typing()) load();
	}, REFRESH_MS);
}

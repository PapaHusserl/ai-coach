// Пульт: план дня. Чистые функции — для тестов (tests/web), DOM — внизу, только в браузере.

const WEEKDAYS = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
const MONTHS = [
	"января", "февраля", "марта", "апреля", "мая", "июня",
	"июля", "августа", "сентября", "октября", "ноября", "декабря",
];
const REFRESH_MS = 60000;

// "2026-11-07T09:05:00" -> "09:05"
export function formatClock(iso) {
	return iso.slice(11, 16);
}

// "2026-11-07" -> "сб, 7 ноября"
export function formatDate(day) {
	const [year, month, date] = day.split("-").map(Number);
	const weekday = new Date(Date.UTC(year, month - 1, date)).getUTCDay();
	return `${WEEKDAYS[weekday]}, ${date} ${MONTHS[month - 1]}`;
}

// Ширина заполненной части бара, 0..100 %.
export function barPercent(elapsedMin, leftMin) {
	const total = elapsedMin + leftMin;
	if (total <= 0) return 0;
	return Math.min(100, Math.max(0, Math.round((elapsedMin / total) * 100)));
}

// "2026-11-07" + 1 -> "2026-11-08"
export function shiftDay(day, delta) {
	const [year, month, date] = day.split("-").map(Number);
	return new Date(Date.UTC(year, month - 1, date + delta)).toISOString().slice(0, 10);
}

// Идёт ли сейчас пункт: current — список {source, id} из /api/day.
export function isCurrent(current, source, id) {
	return current.some((c) => c.source === source && c.id === id);
}

// Строки дня: all_day сверху, остальные по началу; у каждой source, current, muted.
export function dayRows(view) {
	const rows = [
		...view.items.map((row) => ({ ...row, source: "item" })),
		...view.meetings.map((row) => ({ ...row, source: "meeting" })),
	];
	const marked = rows.map((row) => ({
		...row,
		current: isCurrent(view.current, row.source, row.id),
		muted: row.source === "meeting",
	}));
	const order = (a, b) => a.start_at.localeCompare(b.start_at);
	return [...marked.filter((r) => r.all_day).sort(order), ...marked.filter((r) => !r.all_day).sort(order)];
}

// Подпись бара: "прошло 1 ч 30 мин / осталось 2 ч 0 мин".
export function barLabel(elapsedMin, leftMin) {
	const part = (min) => (min >= 60 ? `${Math.floor(min / 60)} ч ${min % 60} мин` : `${min} мин`);
	return `прошло ${part(elapsedMin)} / осталось ${part(leftMin)}`;
}

function rowText(row) {
	const time = row.all_day ? "весь день" : `${formatClock(row.start_at)}–${formatClock(row.end_at)}`;
	const draft = row.status === "draft" ? " (черновик)" : "";
	return [time, `${row.title || "Встреча"}${draft}`];
}

function render(view) {
	document.getElementById("date").textContent = formatDate(view.date);
	document.getElementById("now").textContent = formatClock(view.now);
	document.getElementById("fill").style.width = `${barPercent(view.elapsed_min, view.left_min)}%`;
	document.getElementById("bar-label").textContent = barLabel(view.elapsed_min, view.left_min);
	const list = document.getElementById("rows");
	list.replaceChildren();
	const rows = dayRows(view);
	document.getElementById("empty").hidden = rows.length > 0;
	for (const row of rows) {
		const item = document.createElement("li");
		item.className = ["row", row.muted ? "muted" : "", row.current ? "current" : ""].join(" ").trim();
		const [time, title] = rowText(row);
		const when = document.createElement("span");
		when.className = "when";
		when.textContent = time;
		const what = document.createElement("span");
		what.className = "what";
		what.textContent = title;
		item.append(when, what);
		list.append(item);
	}
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
		} catch (error) {
			message.textContent = `Не удалось загрузить: ${error.message}`;
			message.hidden = false;
		}
	};
	const move = (delta) => {
		const shown = document.body.dataset.day ?? day;
		if (!shown) return;
		day = shiftDay(shown, delta);
		load();
	};
	document.getElementById("prev").addEventListener("click", () => move(-1));
	document.getElementById("next").addEventListener("click", () => move(1));
	load();
	setInterval(load, REFRESH_MS);
}

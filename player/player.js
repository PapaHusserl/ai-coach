// Плеер тренировки: ссылка вида index.html#v1.<сжатая тренировка>.
// Чистые функции экспортированы (их проверяет node --test), DOM-часть — в ui.js.

export const VERSION = 1;
const PREFIX = "v1.";

// Фрагмент "#v1.xxx" -> "xxx" (base64url). Иначе Error с текстом для пользователя.
export function parseFragment(hash) {
	const text = (hash || "").replace(/^#/, "");
	if (!text) {
		throw new Error("Откройте ссылку от тренера.");
	}
	const match = /^v(\d+)\./.exec(text);
	if (match && Number(match[1]) > VERSION) {
		throw new Error("Ссылка от более новой версии тренера — обновите страницу.");
	}
	if (!text.startsWith(PREFIX) || text.length === PREFIX.length) {
		throw new Error("Ссылка повреждена: откройте её у тренера заново.");
	}
	return text.slice(PREFIX.length);
}

export function base64urlToBytes(text) {
	const base64 = text.replace(/-/g, "+").replace(/_/g, "/");
	const binary = atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4));
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) {
		bytes[i] = binary.charCodeAt(i);
	}
	return bytes;
}

// base64url -> JSON-объект (raw deflate).
export async function inflate(body) {
	const stream = new Blob([base64urlToBytes(body)]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
	const text = await new Response(stream).text();
	return JSON.parse(text);
}

// Блок × r -> плоский список шагов. «Подход i/r» — set/of, последний rest остаётся.
// Неизвестный k считается work.
export function expand(payload) {
	const known = ["warmup", "work", "recovery", "cooldown", "rest"];
	const steps = [];
	for (const block of payload.b || []) {
		const repeat = block.r || 1;
		for (let i = 1; i <= repeat; i++) {
			for (const step of block.s || []) {
				steps.push({
					k: known.includes(step.k) ? step.k : "work",
					title: step.t || (step.k === "rest" ? "" : block.t) || "",
					sec: step.sec,
					m: step.m,
					reps: step.reps,
					kg: step.kg,
					pace: step.pace,
					note: step.note || "",
					set: i,
					of: repeat,
				});
			}
		}
	}
	return steps;
}

// Секунды на километр -> "4:15".
function minSec(sec) {
	const total = Math.round(sec);
	return Math.floor(total / 60) + ":" + String(total % 60).padStart(2, "0");
}

// [медленнее, быстрее] в сек/км -> "4:15–4:05/км".
export function formatPace(pace) {
	return minSec(pace[0]) + "–" + minSec(pace[1]) + "/км";
}

// Секунды -> "m:ss" или "h:mm:ss".
export function formatClock(sec) {
	const total = Math.max(0, Math.round(sec));
	const h = Math.floor(total / 3600);
	const m = Math.floor((total % 3600) / 60);
	const s = total % 60;
	const ss = String(s).padStart(2, "0");
	if (h > 0) {
		return h + ":" + String(m).padStart(2, "0") + ":" + ss;
	}
	return m + ":" + ss;
}

// Сумма шагов, заданных временем (шаги по повторам и метрам времени не имеют).
export function totalSeconds(payload) {
	let sum = 0;
	for (const step of expand(payload)) {
		sum += step.sec || 0;
	}
	return sum;
}

// Детерминированный короткий хэш строки (FNV-1a) для UID.
export function hashText(text) {
	let h = 0x811c9dc5;
	for (let i = 0; i < text.length; i++) {
		h ^= text.charCodeAt(i);
		h = Math.imul(h, 0x01000193) >>> 0;
	}
	return h.toString(16).padStart(8, "0");
}

function escapeIcs(text) {
	return String(text).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

function pad2(n) {
	return String(n).padStart(2, "0");
}

function icsLocal(date) {
	return (
		date.getFullYear() + pad2(date.getMonth() + 1) + pad2(date.getDate()) + "T" + pad2(date.getHours()) + pad2(date.getMinutes()) + "00"
	);
}

function icsUtc(date) {
	return (
		date.getUTCFullYear() +
		pad2(date.getUTCMonth() + 1) +
		pad2(date.getUTCDate()) +
		"T" +
		pad2(date.getUTCHours()) +
		pad2(date.getUTCMinutes()) +
		pad2(date.getUTCSeconds()) +
		"Z"
	);
}

// .ics: без tm — событие на весь день, с tm — локальное (плавающее) время.
// fragment — исходный фрагмент без "#" (для UID), url — ссылка на плеер, now — для DTSTAMP.
export function icsText(payload, fragment, url, now = new Date()) {
	const [y, mo, d] = payload.d.split("-").map(Number);
	const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ai-coach//player//RU", "BEGIN:VEVENT"];
	lines.push("UID:" + hashText(fragment) + "@ai-coach");
	lines.push("DTSTAMP:" + icsUtc(now));
	lines.push("SUMMARY:" + escapeIcs(payload.n));
	if (payload.tm) {
		const [hh, mm] = payload.tm.split(":").map(Number);
		const start = new Date(y, mo - 1, d, hh, mm);
		const seconds = payload.dur || totalSeconds(payload) || 3600;
		const end = new Date(start.getTime() + seconds * 1000);
		lines.push("DTSTART:" + icsLocal(start));
		lines.push("DTEND:" + icsLocal(end));
	} else {
		lines.push("DTSTART;VALUE=DATE:" + String(y) + pad2(mo) + pad2(d));
	}
	lines.push("DESCRIPTION:" + escapeIcs("Тренировка: " + url));
	lines.push("URL:" + url);
	lines.push("END:VEVENT", "END:VCALENDAR");
	return lines.join("\r\n") + "\r\n";
}

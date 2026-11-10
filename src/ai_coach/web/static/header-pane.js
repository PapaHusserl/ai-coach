// Пульт: шапка — показатели дня, вес, синк (DOM, в браузере). Тексты строк — header-model.js.

import { metricsLine, syncLine, weightLine } from "./header-model.js";
import { postJson } from "./post.js";
import { toast } from "./toast.js";

const POLL_MS = 5000;
const IDLE = { running: false, started_at: null, error: null };

let timer = null;
let reload = null;

function node(id) {
	return document.getElementById(id);
}

async function fetchStatus() {
	const response = await fetch("/api/sync");
	if (!response.ok) throw new Error(await response.text());
	return response.json();
}

function showError(text) {
	const box = node("header-error");
	box.textContent = text;
	box.hidden = !text;
}

async function poll() {
	let status;
	try {
		status = await fetchStatus();
	} catch (error) {
		console.error("GET /api/sync не удался", error);
		return;
	}
	if (status.running) return;
	clearInterval(timer);
	timer = null;
	reload();
}

function watch() {
	if (timer === null) timer = setInterval(poll, POLL_MS);
}

async function saveWeight() {
	const input = node("weight-input");
	const saved = node("weight-ok");
	saved.disabled = true;
	const result = await postJson("/api/weight", { kg: input.value });
	saved.disabled = false;
	showError(result.text);
	if (!result.ok) return;
	input.value = "";
	node("weight-form").hidden = true;
	toast("Записано");
	reload();
}

// Синк уже идёт (409) — тоже опрос; любой другой отказ — текст, кнопка снова активна.
async function startSync() {
	node("sync-btn").disabled = true;
	const result = await postJson("/api/sync", {});
	if (!result.ok && result.status !== 409) {
		showError(result.text);
		node("sync-btn").disabled = false;
		return;
	}
	showError("");
	node("sync-line").textContent = syncLine({}, { running: true });
	watch();
}

// Занято: идёт опрос синка или фокус в форме веса (клик мимо снимает занятость).
export function headerBusy() {
	const form = node("weight-form");
	return timer !== null || (!form.hidden && form.contains(document.activeElement));
}

// header — day.header; load — перечитать день.
export function renderHeader(header, load) {
	reload = load;
	node("metrics").textContent = metricsLine(header.metrics);
	node("weight-line").textContent = weightLine(header.weight);
	node("sync-line").textContent = syncLine(header.sync, header.sync.running ? { running: true } : IDLE);
	node("sync-btn").disabled = header.sync.running;
	showError(header.sync.error || "");
	if (header.sync.running) watch();
}

if (typeof document !== "undefined") {
	node("weight-btn").addEventListener("click", () => {
		node("weight-form").hidden = false;
		node("weight-input").focus();
	});
	node("weight-ok").addEventListener("click", saveWeight);
	node("weight-input").addEventListener("keydown", (event) => {
		if (event.key === "Enter") saveWeight();
		if (event.key === "Escape") node("weight-form").hidden = true;
	});
	node("sync-btn").addEventListener("click", startSync);
}

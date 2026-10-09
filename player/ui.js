// DOM-часть плеера: экраны, таймер, звук, Wake Lock. Чистые функции — в player.js.
import { VERSION, parseFragment, inflate, expand, formatPace, formatClock, icsText, totalSeconds } from "./player.js";

const KIND_NAMES = {
	warmup: "Разминка",
	work: "Работа",
	recovery: "Восстановление",
	cooldown: "Заминка",
	rest: "Отдых",
};

const SPORT_NAMES = {
	strength: "Силовая",
	mobility: "Растяжка",
	run: "Бег",
	bike: "Вело",
	swim: "Плавание",
};

const NEWER = "Ссылка от более новой версии тренера — обновите страницу.";
const BROKEN = "Ссылка повреждена: откройте её у тренера заново.";

let app = null;
let payload = null;
let steps = [];
const state = { index: 0, left: 0, end: 0, paused: false, running: false, timer: null, audio: null, wake: null };

// ---------- мелкие помощники

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) {
		node.className = className;
	}
	if (text !== undefined) {
		node.textContent = text;
	}
	return node;
}

function button(text, className, onClick) {
	const node = el("button", className, text);
	node.type = "button";
	node.addEventListener("click", onClick);
	return node;
}

function showMessage(text) {
	app.replaceChildren(el("p", "message", text));
}

function formatDate(text) {
	const [y, m, d] = text.split("-");
	return d + "." + m + "." + y;
}

// Что надо сделать на шаге: "12 повт. · 60 кг", "5:00", "400 м".
function stepAmount(step) {
	const parts = [];
	if (step.reps) {
		parts.push(step.reps + " повт.");
	}
	if (step.kg) {
		parts.push(step.kg + " кг");
	}
	if (step.m) {
		parts.push(step.m + " м");
	}
	if (step.sec) {
		parts.push(formatClock(step.sec));
	}
	return parts.join(" · ");
}

function stepName(step) {
	const name = step.title || KIND_NAMES[step.k];
	if (step.of > 1) {
		return name + " · подход " + step.set + "/" + step.of;
	}
	return name;
}

// ---------- звук, вибрация

function beep(long) {
	if (!state.audio) {
		return;
	}
	const now = state.audio.currentTime;
	const length = long ? 0.6 : 0.2;
	const osc = state.audio.createOscillator();
	const gain = state.audio.createGain();
	osc.frequency.value = long ? 660 : 880;
	gain.gain.setValueAtTime(0.3, now);
	gain.gain.exponentialRampToValueAtTime(0.001, now + length);
	osc.connect(gain);
	gain.connect(state.audio.destination);
	osc.start(now);
	osc.stop(now + length);
}

function vibrate(long) {
	if (navigator.vibrate) {
		navigator.vibrate(long ? [300, 100, 300] : 150);
	}
}

function signal(long) {
	beep(long);
	vibrate(long);
}

// Вызывается из обработчика «Старт» — иначе браузер не разблокирует звук.
function unlockAudio() {
	const AudioClass = window.AudioContext || window.webkitAudioContext;
	if (!AudioClass) {
		return;
	}
	state.audio = state.audio || new AudioClass();
	state.audio.resume();
}

// ---------- Wake Lock

async function lockScreen() {
	if (!navigator.wakeLock || state.wake) {
		return;
	}
	try {
		state.wake = await navigator.wakeLock.request("screen");
		state.wake.addEventListener("release", () => {
			state.wake = null;
		});
	} catch (e) {
		state.wake = null;
	}
}

function releaseScreen() {
	if (state.wake) {
		state.wake.release();
	}
}

function onVisibility() {
	if (document.visibilityState === "visible" && state.running) {
		lockScreen();
	}
}

// ---------- таймер и переходы между шагами

function stopTimer() {
	clearInterval(state.timer);
	state.timer = null;
}

function tick() {
	if (state.paused) {
		return;
	}
	state.left = Math.ceil((state.end - Date.now()) / 1000);
	if (state.left <= 0) {
		go(state.index + 1);
		return;
	}
	if (state.left <= 3) {
		beep(false);
	}
	document.getElementById("clock").textContent = formatClock(state.left);
}

function go(index) {
	stopTimer();
	state.index = index;
	state.paused = false;
	if (index >= steps.length) {
		finish();
		return;
	}
	state.left = steps[index].sec || 0;
	signal(false);
	renderStep();
	state.end = Date.now() + state.left * 1000;
	if (state.left > 0) {
		state.timer = setInterval(tick, 1000);
	}
}

function finish() {
	signal(true);
	state.running = false;
	releaseScreen();
	const done = el("div", "player");
	done.append(el("h2", "current", "Тренировка закончена"), el("p", "amount", "Отличная работа!"));
	const controls = el("div", "actions");
	controls.append(button("К списку", "primary", renderList));
	app.replaceChildren(done, controls);
}

// ---------- экран списка

function listMeta() {
	const total = payload.dur || totalSeconds(payload);
	const meta = [formatDate(payload.d)];
	if (payload.tm) {
		meta.push(payload.tm);
	}
	if (SPORT_NAMES[payload.sp]) {
		meta.push(SPORT_NAMES[payload.sp]);
	}
	if (total) {
		meta.push("≈ " + Math.round(total / 60) + " мин");
	}
	return meta.join(" · ");
}

function listSteps() {
	const list = el("ol", "steps");
	for (const step of steps) {
		const item = el("li", "step step-" + step.k);
		item.append(el("span", "step-name", stepName(step)));
		item.append(el("span", "step-amount", stepAmount(step)));
		list.append(item);
	}
	return list;
}

function onStart() {
	state.running = true;
	unlockAudio();
	lockScreen();
	go(0);
}

function onCalendar() {
	const fragment = location.hash.replace(/^#/, "");
	const blob = new Blob([icsText(payload, fragment, location.href)], { type: "text/calendar" });
	const link = el("a");
	link.href = URL.createObjectURL(blob);
	link.download = "trenirovka.ics";
	link.click();
	setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

async function onQr(qrBox) {
	const { default: qrcode } = await import("./vendor/qrcode.mjs");
	const qr = qrcode(0, "L");
	qr.addData(location.href);
	qr.make();
	qrBox.innerHTML = qr.createSvgTag({ scalable: true, margin: 2 });
}

function renderList() {
	stopTimer();
	state.running = false;
	releaseScreen();
	const qrBox = el("div", "qr");
	const actions = el("div", "actions");
	actions.append(
		button("Старт", "primary", onStart),
		button("В календарь", "", onCalendar),
		button("QR этой страницы", "", () => onQr(qrBox)),
	);
	app.replaceChildren(el("h1", "", payload.n), el("p", "meta", listMeta()), actions, qrBox, listSteps());
}

// ---------- экран шага

function stepBody(step) {
	const parts = [];
	if (step.sec) {
		const clock = el("p", "clock", formatClock(state.left));
		clock.id = "clock";
		parts.push(clock);
	} else {
		parts.push(el("p", "amount", stepAmount(step)));
	}
	if (step.sec && (step.kg || step.m)) {
		parts.push(el("p", "amount", stepAmount({ kg: step.kg, m: step.m })));
	}
	if (step.pace) {
		parts.push(el("p", "pace", "Темп " + formatPace(step.pace)));
	}
	if (step.note) {
		parts.push(el("p", "note", step.note));
	}
	return parts;
}

function nextText(next) {
	return next ? "Дальше: " + stepName(next) + " " + stepAmount(next) : "Это последний шаг";
}

function pauseButton() {
	const pause = button(state.paused ? "Продолжить" : "Пауза", "", () => {
		state.paused = !state.paused;
		state.end = Date.now() + state.left * 1000;
		pause.textContent = state.paused ? "Продолжить" : "Пауза";
	});
	return pause;
}

function stepControls(step) {
	const controls = el("div", "actions");
	controls.append(button("Назад", "", () => go(Math.max(0, state.index - 1))));
	if (step.sec) {
		controls.append(pauseButton());
	} else {
		controls.append(button("Готово", "primary", () => go(state.index + 1)));
	}
	controls.append(button("Пропустить", "", () => go(state.index + 1)));
	controls.append(button("К списку", "", renderList));
	return controls;
}

function renderStep() {
	const step = steps[state.index];
	const box = el("div", "player step-" + step.k);
	box.append(el("p", "progress", "Шаг " + (state.index + 1) + " из " + steps.length));
	box.append(el("h2", "current", stepName(step)));
	box.append(...stepBody(step));
	box.append(el("p", "next", nextText(steps[state.index + 1])));
	app.replaceChildren(box, stepControls(step));
}

// ---------- запуск

function begin(data) {
	if (data.v !== VERSION) {
		showMessage(NEWER);
		return;
	}
	payload = data;
	steps = expand(data);
	document.addEventListener("visibilitychange", onVisibility);
	renderList();
}

function parseOrShow() {
	try {
		return parseFragment(location.hash);
	} catch (e) {
		showMessage(e.message);
		return null;
	}
}

function main() {
	app = document.getElementById("app");
	if (typeof DecompressionStream === "undefined") {
		showMessage("Обновите браузер: этот не умеет распаковывать ссылку тренировки.");
		return;
	}
	const body = parseOrShow();
	if (body !== null) {
		inflate(body).then(begin, () => showMessage(BROKEN));
	}
}

main();

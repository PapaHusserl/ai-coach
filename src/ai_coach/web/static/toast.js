// Пульт: всплывающее «Записано» (Р9) — один узел и один таймер на все панели (зовётся в браузере).

import { el } from "./dom.js";

let node = null;
let timer;

export function toast(text) {
	if (!node) {
		node = el("div", "toast");
		node.setAttribute("role", "status");
		document.body.append(node);
	}
	node.textContent = text;
	node.classList.add("show");
	clearTimeout(timer);
	timer = setTimeout(() => node.classList.remove("show"), 1800);
}

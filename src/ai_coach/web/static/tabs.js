// Вкладки пульта: переключение и загрузка панели видимой вкладки (в браузере).

import { loadPantry } from "./pantry-pane.js";
import { loadState } from "./state-pane.js";
import { loadWeek } from "./week-pane.js";

// Вкладка → загрузчик её панели; порядок тот же, что на странице.
const LOADERS = new Map([
	["train", (day, today) => loadWeek(day, today)],
	["food", (day, today) => loadPantry(day, today)],
	["state", (day) => loadState(day)],
]);

// Загружает панель вкладки tab за день day (today — сегодняшний день).
function loadPanel(tab, day, today) {
	const loader = LOADERS.get(tab);
	if (loader) loader(day, today);
}

// После загрузки дня: обновляет панели вкладок, которые сейчас видны.
export function refreshPanels(day, today) {
	for (const tab of LOADERS.keys()) {
		if (!document.querySelector(`[data-panel="${tab}"]`).hidden) loadPanel(tab, day, today);
	}
}

// Клик по вкладке: показать её панель и, если день уже загружен, загрузить её.
export function setupTabs() {
	const tabs = document.querySelectorAll("#tabs button");
	for (const tab of tabs) {
		tab.addEventListener("click", () => {
			for (const other of tabs) other.setAttribute("aria-selected", String(other === tab));
			for (const panel of document.querySelectorAll("[data-panel]")) {
				panel.hidden = panel.dataset.panel !== tab.dataset.tab;
			}
			if (document.body.dataset.day) {
				loadPanel(tab.dataset.tab, document.body.dataset.day, document.body.dataset.today);
			}
		});
	}
}

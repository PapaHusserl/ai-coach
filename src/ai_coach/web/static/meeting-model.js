// Пульт: окно чужой встречи — чистые функции без DOM (тесты — tests/web/meeting.test.mjs).

import { shiftDay } from "./pult-model.js";

const DAY_MS = 86400000;

export const dayOf = (iso) => iso.slice(0, 10);

// Целые сутки от даты a до даты b ("YYYY-MM-DD…"), время не учитывается.
export const dayDiff = (a, b) =>
	Math.round((Date.parse(`${dayOf(b)}T00:00:00Z`) - Date.parse(`${dayOf(a)}T00:00:00Z`)) / DAY_MS);

// ISO-время со сдвигом на целые сутки.
export const shiftIso = (iso, days) => new Date(Date.parse(`${iso.slice(0, 19)}Z`) + days * DAY_MS).toISOString().slice(0, 19);

// Новые start_at / end_at из полей: событие на весь день сдвигается на целые сутки, иначе дата + «с» + «до» (Р18 = 1).
export function newTimes(view, date, from, to) {
	if (view.all_day) {
		const days = dayDiff(view.start_at, `${date}T00:00:00`);
		return { start_at: shiftIso(view.start_at, days), end_at: shiftIso(view.end_at, days) };
	}
	const span = dayDiff(view.start_at, view.end_at);
	const endDay = shiftDay(date, to === "00:00" && span === 0 ? 1 : span);
	return { start_at: `${date}T${from}:00`, end_at: `${endDay}T${to}:00` };
}

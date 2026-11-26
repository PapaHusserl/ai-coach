// Строка «записано: …» окна вечернего чек-ина: часы, уже записанные за день; чистая функция.
const NAMES = [
	["work", "работа"],
	["hobby", "хобби"],
	["rest", "отдых"],
];

// hours — {work, hobby, rest} (только записанные); пусто, null или undefined — "".
export function hoursLine(hours) {
	const parts = NAMES.filter(([key]) => hours?.[key] != null).map(([key, name]) => `${name} ${hours[key]} ч`);
	return parts.length ? `записано: ${parts.join(" · ")}` : "";
}

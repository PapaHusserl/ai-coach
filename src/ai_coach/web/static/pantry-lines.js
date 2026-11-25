// Пульт: строки о списании кладовой после «Съел вариант N» (тесты — tests/web/marks.test.mjs через marks.js).

// Ответ /api/mark, ключ pantry: «Списано из кладовой», «Не списано, нет в кладовой», предупреждения как пришли;
// ничего не списано — одна строка «Из кладовой ничего не списано.» (Р19). Нет pantry (запись «своё») — [].
export function pantryLines(reply) {
	const pantry = reply?.pantry;
	if (!pantry) return [];
	if (!pantry.used.length) return ["Из кладовой ничего не списано."];
	const lines = [`Списано из кладовой: ${pantry.used.join(", ")}.`];
	if (pantry.skipped.length) lines.push(`Не списано, нет в кладовой: ${pantry.skipped.join(", ")}.`);
	return [...lines, ...pantry.warnings];
}

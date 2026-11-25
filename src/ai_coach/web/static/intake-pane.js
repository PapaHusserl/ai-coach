// Пульт: блок «Добавки к приёму» в окне еды (П8, Р7–Р18), только DOM. Тесты — tests/web/marks-intake.test.mjs.
import { el } from "./dom.js";
import { postJson } from "./post.js";
import { toast } from "./toast.js";

// POST /api/intake {kind, item_id, date, taken}: записано — reload() перечитывает день, иначе текст отказа во всплывашке (Р22).
export async function postIntake(item, taken, day, reload) {
	const result = await postJson("/api/intake", { kind: item.kind, item_id: item.id, date: day, taken });
	if (result.ok) await reload();
	else toast(result.text);
}

// Строки блока: «[✓ ]имя · доза единица[ · когда]»; единица как в `coach med list` (iu, mg), доза без «.0» (Р10, Р18).
export function intakeRows(meal) {
	return meal.intake.map((item) => {
		const parts = [`${item.name} · ${item.dose} ${item.unit}`];
		if (item.time_note) parts.push(item.time_note);
		return { item, text: `${item.taken ? "✓ " : ""}${parts.join(" · ")}` };
	});
}

// Блок: заголовок и строка на позицию. onToggle(item, taken) — клик по строке, taken наоборот (Р9, Р17);
// onToggle нет (будущий день) — строки текстом (Р12). Нет позиций — null: блока и заголовка нет (Р10 а).
export function intakeBlock(meal, onToggle) {
	const rows = intakeRows(meal);
	if (!rows.length) return null;
	const block = el("div", "intake");
	block.append(el("p", "bar-label", "Добавки к приёму"));
	for (const { item, text } of rows) {
		if (!onToggle) {
			block.append(el("p", "intake-row", text));
			continue;
		}
		const button = el("button", "intake-row", text);
		button.type = "button";
		button.setAttribute("aria-pressed", String(item.taken));
		button.addEventListener("click", () => onToggle(item, item.taken ? 0 : 1));
		block.append(button);
	}
	return block;
}

// Блок как список узлов окна: пусто или один блок.
export function intakeNodes(meal, onToggle) {
	return [intakeBlock(meal, onToggle)].filter(Boolean);
}

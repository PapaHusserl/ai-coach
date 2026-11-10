// Пульт: модель вкладки «Еда» — чистые функции без DOM (тесты — tests/web/pantry.test.mjs).

const STEPS = { g: 50, ml: 100, pcs: 1 };
const DELTA = /^([+-]?)(\d+(?:\.\d+)?)$/;
const OPS = { "+": "add", "-": "use", "": "set" };

// Шаг кнопок «−»/«+» по единице (Р6 = 1).
export function stepFor(unit) {
	return STEPS[unit];
}

// «+200» — добавить, «-50» — списать, «120» — сверка; не число, «+0», «-0» — null.
export function parseDelta(text) {
	const found = DELTA.exec(text.trim());
	if (!found) return null;
	const [, sign, digits] = found;
	const qty = Number(digits);
	if (sign && qty === 0) return null;
	return { op: OPS[sign], qty };
}

// Строки таблицы: state — по флагам сервера (день просмотра), spoil — по настоящему today.
export function pantryRows(view, today) {
	return view.rows.map((row) => ({
		item: row.item,
		qty: row.qty,
		unit: row.unit,
		step: stepFor(row.unit),
		until: row.expires_on ?? "",
		state: row.expired ? "expired" : row.soon ? "soon" : "",
		spoil: row.expires_on !== null && row.expires_on < today,
	}));
}

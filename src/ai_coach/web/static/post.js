// Пульт: POST JSON с текстом отказа для пользователя (зовётся в браузере). Общий для шапки и кладовой.

export async function postJson(url, payload) {
	try {
		const response = await fetch(url, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		});
		if (response.ok) return { ok: true, status: response.status, text: "", body: await response.text() };
		const text = (await response.text()).trim();
		const known = [400, 404, 409].includes(response.status);
		const shown = known ? text : `Не сохранилось, ошибка пульта (код ${response.status})`;
		return { ok: false, status: response.status, text: shown };
	} catch (error) {
		console.error(`POST ${url} не удался`, error);
		return { ok: false, status: 0, text: "Не сохранилось, нет связи с пультом" };
	}
}

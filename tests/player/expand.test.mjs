import test from "node:test";
import assert from "node:assert/strict";
import { expand, totalSeconds } from "../../player/player.js";

test("r умножает шаги блока", () => {
	const payload = { b: [{ r: 3, s: [{ k: "work", reps: 8 }, { k: "rest", sec: 60 }] }] };
	assert.equal(expand(payload).length, 6);
});

test("подход i/r", () => {
	const payload = { b: [{ r: 2, s: [{ k: "work", reps: 8 }] }] };
	const steps = expand(payload);
	assert.deepEqual(
		steps.map((s) => [s.set, s.of]),
		[[1, 2], [2, 2]],
	);
});

test("последний rest остаётся", () => {
	const payload = { b: [{ r: 2, s: [{ k: "work", reps: 8 }, { k: "rest", sec: 60 }] }] };
	const steps = expand(payload);
	assert.equal(steps[steps.length - 1].k, "rest");
});

test("неизвестный k считается work", () => {
	const steps = expand({ b: [{ r: 1, s: [{ k: "dance" }] }] });
	assert.equal(steps[0].k, "work");
});

test("без r блок идёт один раз", () => {
	assert.equal(expand({ b: [{ s: [{ k: "work" }] }] }).length, 1);
});

test("название шага важнее названия блока", () => {
	const steps = expand({ b: [{ r: 1, t: "Блок", s: [{ k: "work", t: "Шаг" }] }] });
	assert.equal(steps[0].title, "Шаг");
});

test("название блока, если у шага нет своего", () => {
	const steps = expand({ b: [{ r: 1, t: "Блок", s: [{ k: "work" }] }] });
	assert.equal(steps[0].title, "Блок");
});

test("поля шага переносятся", () => {
	const steps = expand({ b: [{ r: 1, s: [{ k: "work", m: 1000, pace: [255, 245], note: "ровно" }] }] });
	assert.deepEqual([steps[0].m, steps[0].pace, steps[0].note], [1000, [255, 245], "ровно"]);
});

test("пустая тренировка -> нет шагов", () => {
	assert.deepEqual(expand({}), []);
});

test("totalSeconds суммирует sec с учётом повторов", () => {
	const payload = { b: [{ r: 3, s: [{ k: "work", reps: 8 }, { k: "rest", sec: 120 }] }, { r: 1, s: [{ k: "work", m: 400 }] }] };
	assert.equal(totalSeconds(payload), 360);
});

test("totalSeconds без времени == 0", () => {
	assert.equal(totalSeconds({ b: [{ r: 1, s: [{ k: "work", reps: 5 }] }] }), 0);
});

test("rest без своего названия не берёт название блока", () => {
	const steps = expand({ b: [{ r: 1, t: "Присед", s: [{ k: "work" }, { k: "rest", sec: 60 }] }] });
	assert.ok(!steps[1].title);
});

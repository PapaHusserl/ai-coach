import test from "node:test";
import assert from "node:assert/strict";
import { formatPace, formatClock } from "../../player/player.js";

test("formatPace [255,245]", () => {
	assert.equal(formatPace([255, 245]), "4:15–4:05/км");
});

test("formatPace секунды с нулём", () => {
	assert.equal(formatPace([305, 300]), "5:05–5:00/км");
});

test("formatClock 65", () => {
	assert.equal(formatClock(65), "1:05");
});

test("formatClock 3725", () => {
	assert.equal(formatClock(3725), "1:02:05");
});

test("formatClock 0", () => {
	assert.equal(formatClock(0), "0:00");
});

test("formatClock отрицательное -> 0:00", () => {
	assert.equal(formatClock(-5), "0:00");
});

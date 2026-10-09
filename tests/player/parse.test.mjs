import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseFragment, inflate } from "../../player/player.js";

function fixture(name) {
	return JSON.parse(readFileSync(new URL("../fixtures/links/" + name + ".json", import.meta.url), "utf8"));
}

for (const name of ["strength", "stretch", "run"]) {
	test("parse+inflate " + name + " == payload", async () => {
		const data = fixture(name);
		const body = parseFragment("#" + data.fragment);
		assert.deepEqual(await inflate(body), data.payload);
	});
}

test("hash без решётки тоже разбирается", () => {
	assert.equal(parseFragment("v1.abc"), "abc");
});

test("v2. -> ошибка про новую версию", () => {
	assert.throws(() => parseFragment("#v2.abc"), /новой версии/);
});

test("пустой hash -> откройте ссылку", () => {
	assert.throws(() => parseFragment(""), /Откройте ссылку/);
});

test("только решётка -> откройте ссылку", () => {
	assert.throws(() => parseFragment("#"), /Откройте ссылку/);
});

test("undefined -> откройте ссылку", () => {
	assert.throws(() => parseFragment(undefined), /Откройте ссылку/);
});

test("мусор без префикса -> ошибка", () => {
	assert.throws(() => parseFragment("#мусор"), /повреждена/);
});

test("v1. без тела -> ошибка", () => {
	assert.throws(() => parseFragment("#v1."), /повреждена/);
});

test("inflate мусорного тела -> ошибка", async () => {
	await assert.rejects(inflate("AAAA"));
});

test("v0. -> общая ошибка ссылки, не про новую версию", () => {
	assert.throws(() => parseFragment("#v0.abc"), (e) => /повреждена/.test(e.message) && !/новой версии/.test(e.message));
});

"""П7 партия 3: таблица слов погоды в weather.py и в weather-model.js - одна и та же."""

import re
from pathlib import Path

from ai_coach.weather import WORDS

JS = Path(__file__).resolve().parent.parent / "src/ai_coach/web/static/weather-model.js"


def js_words() -> dict[int, str]:
    pairs = re.findall(r"""["']?(\d+)["']?\s*:\s*["']([^"']+)["']""", JS.read_text())
    return {int(code): word for code, word in pairs}


def test_every_python_word_is_in_js() -> None:
    table = js_words()
    missing = {code: word for code, word in WORDS.items() if table.get(code) != word}
    assert missing == {}


def test_every_js_word_is_in_python() -> None:
    extra = {code: word for code, word in js_words().items() if WORDS.get(code) != word}
    assert extra == {}

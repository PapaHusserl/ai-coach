"""Симптомы и температура в свободном тексте: слова-основы, отрицания, число температуры."""

import re

# Явные симптомы простуды (ряд WURSS-24): основа (подстрока текста в нижнем регистре) -> слово.
SYMPTOMS = (
    ("горл", "горло"),
    ("насморк", "насморк"),
    ("сопл", "сопли"),
    ("температур", "температура"),
    ("кашл", "кашель"),
    ("кашел", "кашель"),
    ("залож", "заложенность"),
    ("чиха", "чихание"),
    ("чихн", "чихание"),
    ("перш", "першение"),
    ("осип", "осиплость"),
    ("охрип", "осиплость"),
    ("озноб", "озноб"),
    ("зноб", "озноб"),
    ("ломот", "ломота"),
    ("ломит", "ломота"),
    ("простуд", "простуда"),
    ("простыл", "простуда"),
)
# Температура не ниже порога - и симптом, и тяжёлый признак (Н33).
FEVER_FROM = 37.0
# Отрицание снимает симптом только вплотную: слово(а) перед симптомом или после него.
NEGATIONS_BEFORE = (("нет",), ("без",), ("ни",), ("не", "было"))
NEGATIONS_AFTER = (
    ("нет",),
    ("прошёл",),
    ("прошел",),
    ("прошло",),
    ("прошла",),
    ("прошли",),
    ("не", "болит"),
    ("не", "беспокоит"),
)
# Граница отрезка: знак препинания, скобка, перевод строки, тире.
# Запятая и точка между цифрами - дробь.
_BOUNDARY = re.compile(r"(?<!\d)[.,]|[.,](?!\d)|[;:()\[\]\n—–]| - ")
_TOKEN = re.compile(r"\d+(?:[.,]\d+)?|[^\W\d_]+")
_TEMPERATURE_NUMBER = re.compile(r"\d{2}(?:[.,]\d+)?")

Mention = tuple[str, float | None]


def _negated(tokens: list[str], i: int) -> bool:
    before = any(tuple(tokens[max(i - len(p), 0) : i]) == p for p in NEGATIONS_BEFORE)
    after = any(tuple(tokens[i + 1 : i + 1 + len(p)]) == p for p in NEGATIONS_AFTER)
    return before or after


def _number_after(tokens: list[str], i: int) -> float | None:
    """Число температуры сразу после слова «температур…»; иначе None."""
    if "температур" not in tokens[i] or i + 1 >= len(tokens):
        return None
    following = tokens[i + 1]
    if not _TEMPERATURE_NUMBER.fullmatch(following):
        return None
    return float(following.replace(",", "."))


def _part_mentions(tokens: list[str]) -> list[Mention]:
    found: list[Mention] = []
    for i, token in enumerate(tokens):
        words = {word for stem, word in SYMPTOMS if stem in token}
        if words and not _negated(tokens, i):
            number = _number_after(tokens, i)
            found.extend((word, number) for word in words)
    return found


def _mentions(texts: list[str]) -> list[Mention]:
    """Упоминания симптомов без отрицания: (слово, число температуры или None). Тексты и отрезки
    между знаками препинания разбираются по одному."""
    return [
        mention
        for text in texts
        for part in _BOUNDARY.split(text.lower())
        for mention in _part_mentions(_TOKEN.findall(part))
    ]


def find_symptoms(texts: list[str]) -> list[str]:
    """Слова-симптомы из текстов самочувствия: без повторов, в порядке SYMPTOMS. Температура с
    числом ниже FEVER_FROM - не симптом."""
    present = {word for word, number in _mentions(texts) if number is None or number >= FEVER_FROM}
    return [word for word in dict.fromkeys(w for _, w in SYMPTOMS) if word in present]


def find_fever(texts: list[str]) -> float | None:
    """Наибольшее число температуры в текстах, если оно не ниже FEVER_FROM; иначе None."""
    numbers = [number for _, number in _mentions(texts) if number is not None]
    top = max(numbers, default=None)
    return top if top is not None and top >= FEVER_FROM else None

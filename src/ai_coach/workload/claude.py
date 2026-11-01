"""Счётчики из транскриптов Claude Code (~/.claude/projects): только чтение, в базу идут числа.

Реплика пользователя, вопросы-решения (AskUserQuestion), каталоги проектов и переключения между
ними по дням 04:00-04:00. Субагенты (subagents/), служебные строки, SDK-агенты и сессии тренера
(agent-setting = coach) не считаются. Тексты и полные пути в базу не идут - только короткие имена
каталогов в raw_json счётчика claude_repos.
"""

import json
from datetime import date, datetime, time, timedelta, tzinfo
from pathlib import Path
from typing import Any, cast

SOURCE = "claude"
CLAUDE_COUNTERS = (
    "claude_prompts",
    "claude_prompts_evening",
    "claude_decisions",
    "claude_repos",
    "claude_switches",
)
SERVICE_PREFIXES = ("<", "[Request interrupted")
COACH_AGENT = "coach"
DAY_STARTS = time(4, 0)
EVENING_FROM_HOUR = 19
SDK_ENTRYPOINT = "sdk-cli"
QUESTION_TOOL = "AskUserQuestion"
WORKTREES = "/.claude/worktrees/"
UNKNOWN_REPO = "unknown"
MARKERS = ('"type":"user"', '"type":"assistant"', '"agent-setting"')

Prompt = tuple[datetime, str, bool, str, str]


class ClaudeError(Exception):
    """Каталог транскриптов или файл в нём не читается."""


def _obj(value: Any) -> dict[str, Any]:
    """Объект JSON как словарь; не объект - пустой."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _load(line: str) -> dict[str, Any]:
    """Строка jsonl как словарь; битая или не объект - пустой."""
    try:
        return _obj(json.loads(line))
    except ValueError:
        return {}


def _text(content: Any) -> str:
    """Текст реплики: строка как есть, у списка блоков - первый text; tool_result - пусто."""
    if isinstance(content, str):
        return content
    blocks = [_obj(b) for b in (cast(list[Any], content) if isinstance(content, list) else [])]
    if any(b.get("type") == "tool_result" for b in blocks):
        return ""
    texts = [str(b.get("text")) for b in blocks if b.get("type") == "text"]
    return texts[0] if texts else ""


def _is_prompt(record: dict[str, Any]) -> bool:
    """Реплика пользователя: user, не мета и не сводка сжатия, не SDK-агент, не tool_result,
    текст не служебный (начинается не с `<` и не с `[Request interrupted`)."""
    if record.get("type") != "user" or record.get("isMeta") or record.get("isCompactSummary"):
        return False
    if record.get("entrypoint") == SDK_ENTRYPOINT:
        return False
    text = _text(_obj(record.get("message")).get("content")).lstrip()
    return bool(text) and not text.startswith(SERVICE_PREFIXES)


def _day(ts: str, tz: tzinfo | None = None) -> tuple[str, bool]:
    """День самочувствия (местное время минус 4 ч) и признак вечера (с 19:00 до 04:00) по
    времени записи ISO UTC; tz - пояс (None - системный)."""
    local = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)
    day = (local - timedelta(hours=DAY_STARTS.hour)).date().isoformat()
    return day, local.hour >= EVENING_FROM_HOUR or local.hour < DAY_STARTS.hour


def _agent_of(lines: list[str]) -> str | None:
    """Имя агента сессии из записи agent-setting; нет записи - None."""
    for line in (x for x in lines if '"agent-setting"' in x):
        found = _load(line)
        if found.get("type") == "agent-setting":
            return str(found.get("agentSetting"))
    return None


def _count_questions(block: Any) -> int:
    """Число вопросов в tool_use AskUserQuestion; другой блок или нет questions - 0."""
    found = _obj(block)
    if found.get("type") != "tool_use" or found.get("name") != QUESTION_TOOL:
        return 0
    questions = _obj(found.get("input")).get("questions")
    return len(cast(list[Any], questions)) if isinstance(questions, list) else 0


def _repo_name(cwd: str) -> str:
    """Короткое имя проекта по cwd: последняя часть пути; worktree (…/.claude/worktrees/x)
    сводится к проекту до него."""
    path = cwd.split(WORKTREES)[0].rstrip("/")
    return path.rsplit("/", 1)[-1] or UNKNOWN_REPO


def _mtime_floor(start: date, tz: tzinfo | None) -> float:
    return datetime.combine(start, DAY_STARTS, tzinfo=tz).timestamp()


def _files(root: Path, floor: float) -> list[Path]:
    """Основные файлы root/*/*.jsonl с mtime не раньше floor (subagents/ не обходится)."""
    try:
        folders = sorted(p for p in root.iterdir() if p.is_dir())
        found = [f for folder in folders for f in sorted(folder.glob("*.jsonl"))]
        return [f for f in found if f.stat().st_mtime >= floor]
    except OSError:
        raise ClaudeError("каталог транскриптов не читается") from None


def _records(path: Path) -> tuple[list[dict[str, Any]], bool]:
    """Разобранные записи user/assistant файла и признак сессии тренера; битая строка
    пропускается."""
    try:
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if any(m in line for m in MARKERS)
        ]
    except OSError:
        raise ClaudeError("файл транскрипта не читается") from None
    records = [_load(line) for line in lines]
    found = [r for r in records if r.get("type") in ("user", "assistant")]
    return found, _agent_of(lines) == COACH_AGENT


def _asked(record: dict[str, Any]) -> int:
    """Вопросы-решения в записи assistant: сумма по блокам content."""
    content = _obj(record.get("message")).get("content")
    if record.get("type") != "assistant" or not isinstance(content, list):
        return 0
    return sum(_count_questions(b) for b in cast(list[Any], content))


def _stamp(record: dict[str, Any], tz: tzinfo | None) -> tuple[datetime, str, bool] | None:
    """Время, день и признак вечера записи; нет или битая метка - None."""
    stamp = record.get("timestamp")
    if not isinstance(stamp, str):
        return None
    try:
        day, evening = _day(stamp, tz)
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")), day, evening
    except ValueError:
        return None


def _scan(
    files: list[Path], tz: tzinfo | None, days: set[str]
) -> tuple[list[Prompt], dict[str, int], int]:
    """Реплики окна (время, день, вечер, каталог, cwd), вопросы-решения по дням и число
    разобранных записей окна (в том числе сессий тренера, они в счётчики не идут)."""
    prompts: list[Prompt] = []
    decisions: dict[str, int] = {}
    seen = 0
    for path in files:
        records, coach = _records(path)
        for record in records:
            found = _stamp(record, tz)
            if found is None or found[1] not in days:
                continue
            seen += 1
            if coach:
                continue
            moment, day, evening = found
            if _is_prompt(record):
                cwd = str(record.get("cwd") or "")
                prompts.append((moment, day, evening, path.parent.name, cwd))
            decisions[day] = decisions.get(day, 0) + _asked(record)
    return prompts, decisions, seen


def _names(prompts: list[Prompt]) -> dict[str, str]:
    """Имя проекта для каждого каталога: по самому короткому cwd его реплик (подкаталог
    сводится к корню проекта)."""
    cwds: dict[str, list[str]] = {}
    for _, _, _, folder, cwd in prompts:
        cwds.setdefault(folder, [])
        if cwd:
            cwds[folder].append(cwd)
    return {f: _repo_name(min(c, key=len)) if c else UNKNOWN_REPO for f, c in cwds.items()}


def _day_values(
    todays: list[Prompt], names: dict[str, str], decisions: int
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Значения счётчиков дня и проекты дня ([{repo, prompts}] по убыванию реплик)."""
    sequence = [names[p[3]] for p in sorted(todays, key=lambda p: p[0])]
    tally: dict[str, int] = {}
    for name in sequence:
        tally[name] = tally.get(name, 0) + 1
    repos = [
        {"repo": r, "prompts": n} for r, n in sorted(tally.items(), key=lambda t: (-t[1], t[0]))
    ]
    values = {
        "claude_prompts": len(todays),
        "claude_prompts_evening": sum(1 for p in todays if p[2]),
        "claude_decisions": decisions,
        "claude_repos": len(repos),
        "claude_switches": sum(1 for a, b in zip(sequence, sequence[1:], strict=False) if a != b),
    }
    return values, repos


def read_claude(
    root: Path, start: date, end: date, tz: tzinfo | None = None
) -> list[dict[str, Any]]:
    """Счётчики Claude Code за каждый день start..end включительно (в том числе 0): реплики,
    вечерние реплики, вопросы-решения, проекты (raw_json {"repos": [{repo, prompts}]}) и
    переключения между ними. Читаются файлы с mtime не раньше начала окна. Нет каталога -
    пусто. tz - пояс (по умолчанию системный)."""
    return scan_claude(root, start, end, tz)[0]


def scan_claude(
    root: Path, start: date, end: date, tz: tzinfo | None = None
) -> tuple[list[dict[str, Any]], int, int]:
    """Как read_claude, плюс число прочитанных файлов и число разобранных записей окна:
    файлы есть, записей 0 - формат не распознан."""
    if not root.is_dir():
        return [], 0, 0
    span = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    days = {d.isoformat() for d in span}
    files = _files(root, _mtime_floor(start, tz))
    prompts, decisions, seen = _scan(files, tz, days)
    names = _names(prompts)
    counters: list[dict[str, Any]] = []
    for day in sorted(days):
        todays = [p for p in prompts if p[1] == day]
        values, repos = _day_values(todays, names, decisions.get(day, 0))
        for kind in CLAUDE_COUNTERS:
            row: dict[str, Any] = {"date": day, "kind": kind, "value": values[kind]}
            row["source"] = SOURCE
            if kind == "claude_repos":
                row["raw_json"] = {"repos": repos}
            counters.append(row)
    return counters, len(files), seen

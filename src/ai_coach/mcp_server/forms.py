"""Инструменты MCP: формы тренера (отдельно от tools.py из-за размера).

Тренер заводит форму после «да» пользователя и снимает её; ответы пишет пользователь в пульте.
"""

import json
import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.agenda import AgendaError
from ai_coach.agenda.forms import check_form
from ai_coach.mcp_server import tools
from ai_coach.mcp_server.tools import cap, period
from ai_coach.store.forms import add_form, get_form, list_form_log, list_forms
from ai_coach.store.forms import archive_form as store_archive


def _object(row: dict[str, Any], column: str) -> dict[str, Any]:
    """Строка с колонкой <имя>_json как объектом под именем <имя>."""
    name = column.removesuffix("_json")
    return {k: v for k, v in row.items() if k != column} | {name: json.loads(row[column])}


def create_form(
    conn: sqlite3.Connection, name: str, title: str, fields: list[dict[str, Any]]
) -> dict[str, Any]:
    """Завести форму (после «да» пользователя). name - латиница, цифры, _, с буквы, до 24
    знаков, не имя готового опросника; title - название до 24 знаков; fields - от 1 до 8 полей
    {key, type, label до 40 знаков, required (true/false, по умолчанию true), unit, min, max,
    low, high, options}. type: number (min, max, unit до 8 знаков - только у number), scale
    (целое 1-5; полюса low и high до 24 знаков обязательны; ключ score - «Самочувствие» из
    журнала самочувствия, без полюсов), yesno, choice (options - от 2 до 6 вариантов, каждый
    до 24 знаков). Форма не правится: новая или
    archive_form. Событие с формой: create_draft_event(survey="form:<name>")."""
    try:
        check_form({"name": name, "title": title, "fields": fields})
    except AgendaError as e:
        raise ToolError(str(e)) from None
    if get_form(conn, name) is not None:
        raise ToolError(f"Форма {name} уже есть (активная или снятая): нужно другое имя.")
    with conn:
        add_form(
            conn,
            {
                "name": name,
                "title": title.strip(),
                "fields_json": fields,
                "created_at": tools.now().isoformat(sep=" ", timespec="seconds"),
            },
        )
    return {"name": name}


def archive_form(conn: sqlite3.Connection, name: str) -> dict[str, Any]:
    """Снять форму: новые события с ней не создаются; созданные продолжают работать."""
    stamp = tools.now().isoformat(sep=" ", timespec="seconds")
    with conn:
        archived = store_archive(conn, name, stamp)
    if not archived:
        raise ToolError(f"Активной формы {name} нет.")
    return {"archived": name}


def forms(conn: sqlite3.Connection) -> dict[str, Any]:
    """Активные формы: name, title, fields (список полей объектом), created_at."""
    return cap([_object(row, "fields_json") for row in list_forms(conn)])


def form_log(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, Any]:
    """Ответы форм за период (включительно, до 92 дней): id, date, time, event_id, form,
    values (ответы по ключам полей объектом), score (оценка самочувствия, если у формы есть поле
    score; иначе null), text. Только чтение: отвечает пользователь в пульте."""
    period(date_from, date_to)
    rows = [_object(row, "values_json") for row in list_form_log(conn, date_from, date_to)]
    return cap(rows, newest=True)

"""MCP-сервер (stdio) для Claude Code: читает агрегаты, пишет черновики и КБЖУ еды."""

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ai_coach.mcp_server import agenda, habits, links, review, tools, workload
from ai_coach.mcp_server import overload as overload_tool
from ai_coach.mcp_server.tools import MAX_CHARS, MAX_ROWS
from ai_coach.store.db import open_db

INSTRUCTIONS = (
    "Данные тренера: агрегаты из базы ai-coach (без сырых ответов Garmin). Даты YYYY-MM-DD. "
    f"Списки — не больше {MAX_ROWS} строк и {MAX_CHARS} символов: ответ {{rows, truncated}}, "
    "truncated=true — что-то отрезано (у рядов по датам остаются самые новые строки). "
    "Записать можно только черновики (create_draft_workout, cancel_draft_workout — только draft, "
    "create_draft_event, cancel_draft_event — только draft, propose_phase) и КБЖУ записи еды, "
    "у которой его ещё нет (save_food_nutrition). "
    "Отправки на часы нет: утверждает и отправляет пользователь командами coach approve/push. "
    "Для телефона без часов: get_workout_link даёт ссылку на страницу с тренировкой, "
    "покажи её пользователю как есть. "
    "Нагрузка вне тренировок (get_workload): календарь, туду и груминг берутся из базы, "
    "их кладёт coach sync; к календарю MCP не ходит; названия событий — только "
    "get_workload(events=true) на один день. "
    "Недельный обзор (get_weekly_review): цифры по неделям Пн-Вс и дельты, без выводов; "
    "в сводке week_review_due - пора проводить обзор, после обзора тренер "
    "отмечает его командой coach review done (CLI, не MCP). "
    "События в календаре тренера (get_agenda): MCP пишет только черновики, в календарь их "
    "кладёт пользователь командой coach event write (CLI, не MCP)."
)

# имя инструмента -> (функция из tools.py, описание для Claude)
TOOLS: dict[str, tuple[Callable[..., Any], str]] = {
    "get_morning_snapshot": (
        tools.morning_snapshot,
        "Утренний разбор одним вызовом: метрики, активности, нагрузка, цели, фазы, план, "
        "план/факт, вес, еда за день, продукты дома (до 30 строк), "
        "recipes (имена и КБЖУ на 100 г, до 30), "
        "meal_plan_today (рацион на сегодня уже предложен), "
        "first_run_today (первый запуск тренера за день: синхронизаций за дату не больше одной), "
        "самочувствие за 30 дней (все записи, до 60), отклонения, "
        "workload (нагрузка вне тренировок за 7 дней: часы встреч, вечера, туду, груминг), "
        "workload_ahead (календарь на 7 дней вперёд, без названий и счётчиков; overloaded - "
        "день перегружен только по календарю, без тренировок: нет флага - не гарантия), "
        "overload (как get_overload), evening_done_today (чек-ин сделан), "
        "sport_nutrition_today (питание к тренировкам дня и добавки с пометкой принято; "
        "нет - не отдаётся), "
        "habits_today (привычки на день самочувствия: name, unit, done true - сделано, false - "
        "отмечено «нет», null - не отмечена, amount; нет привычек - rows пуст), "
        "meds_today (курсы на сегодня; "
        "training_day/before/after - только в день тренировки; нет - не отдаётся), "
        "catalog (сколько протоколов, добавок, курсов в справочниках; 0 - пусто), "
        "agenda (события тренера в календаре: черновики и записанные, день назад и 7 вперёд). "
        "date — YYYY-MM-DD (сегодня).",
    ),
    "get_daily_metrics": (
        tools.daily_metrics,
        "Сон, HRV, Body Battery, стресс, readiness по дням.",
    ),
    "get_activities": (tools.activities, "Активности за период."),
    "get_strength_sets": (tools.strength_sets, "Подходы силовой активности."),
    "get_workload": (
        workload.workload,
        "Нагрузка вне тренировок по дням (date_from, date_to - YYYY-MM-DD, до 92 дней): "
        "weekend (сб/вс); work/personal/hobby/rest_hours "
        "(часы встреч календаря) и _evening_hours "
        "(после 19:00); all_day_work (рабочее событие на весь день); счётчики todo_open "
        "(снимок на дату последнего sync), todo_closed (закрыто за день), grooming_done, "
        "grooming_pending (null - не считались). events=true - только на один день "
        "(date_from = date_to): ещё и events с названиями. Пишет coach sync.",
    ),
    "get_overload": (
        overload_tool.overload,
        "Общая нагрузка и сигналы перегруза (date - YYYY-MM-DD): total - нагрузка дня одним "
        "числом (тренировки + работа + хобби + вечер/выходные + туду и груминг), days - 7 дней "
        "до date (date, total, ручные часы manual_work/hobby/rest_hours, null - не вводились), "
        "signals - total_streak, evening_streak, weekend_work, recovery_drop, todo_growth "
        "(kind, value, limit; у recovery_drop value и limit - объекты по readiness/mood/stress); "
        "пустой список - перегруза нет. Нет нагрузки тренировок - "
        "TSS считается нулём, причина в load_error. Ручные часы пишет coach feel.",
    ),
    "get_goals": (tools.goals_list, "Цели; status: active / done / cancelled, без него — все."),
    "get_goals_on": (tools.goals_on, "Какие цели были на конец дня."),
    "get_phases": (
        tools.phases_list,
        "Фазы; status: proposed / accepted / rejected, без него — все.",
    ),
    "get_plan": (
        tools.plan,
        "Запланированные тренировки (черновики, утверждённые, отправленные).",
    ),
    "get_plan_actual": (
        tools.plan_actual,
        "Сопоставление плана и факта: done / skipped / extra / different.",
    ),
    "get_load": (
        tools.load,
        "TSS, CTL, ATL по дням плюс thresholds: {вид: {lthr, source, date}} и warnings "
        "(виды без порога, их TSS 0) (пульс покоя и "
        "пороги по видам берутся из базы, их кладёт coach sync; source: garmin_lt, "
        "garmin_zones, derived — посчитан по бегу или по max HR).",
    ),
    "get_weights": (tools.weights, "Замеры веса."),
    "get_food": (tools.food, "Записи еды (текст и КБЖУ, если посчитаны)."),
    "get_wellbeing": (
        tools.wellbeing,
        "Самочувствие (оценка 1-5, текст, mood и stress 1-5 из вечернего чек-ина - null, если не "
        "спрашивали) по времени; основная оценка дня - последняя запись. "
        "Пишет пользователь командой coach feel.",
    ),
    "get_deviations": (
        tools.deviations,
        "Отклонения за день (плохое самочувствие, readiness, HRV, сон, ATL - CTL); пустой "
        "список - всё в норме, пересчёт плана не нужен. date - YYYY-MM-DD.",
    ),
    "get_profile": (
        tools.profile,
        "Профиль спортсмена на дату (по умолчанию сегодня): пол, возраст, рост, вес, уровень "
        "активности, травмы, инвентарь, расписание, цель по весу и т.д. с источниками (manual / "
        "garmin), age, weight_kg, resting_hr, missing (что не заполнено; goals - нет целей), "
        "nutrition (BMR, TDEE, kcal_target, белки/жиры/углеводы, допущения). "
        "history=true - ещё и все записи по ключам. "
        "Пишет пользователь командой coach profile set.",
    ),
    "get_pantry": (
        tools.pantry,
        "Продукты дома (остаток больше 0): item, qty, unit (g/ml/pcs), updated_at, "
        "expires_on (ближайший срок годности или null), opened (0/1). "
        "Меняет пользователь командами coach pantry.",
    ),
    "get_recipes": (
        tools.recipes,
        "Справочник рецептов: id, name, kcal_100, protein_100, fat_100, carbs_100 (на 100 г "
        "готового), yield_g (вес готового или null), items (product, qty, unit). "
        "Меняет пользователь командами coach recipe.",
    ),
    "get_practices": (
        habits.practices,
        "Справочник практик восстановления: id, name, kind (breathing/pause/walk/sleep), "
        "minutes, trigger (когда применять или null), steps (шаги текстом). "
        "Меняет пользователь командами coach practice.",
    ),
    "get_habits": (
        habits.habits,
        "Привычки: id, name, unit (единица числа или null). Меняет пользователь командами "
        "coach habit.",
    ),
    "get_habit_log": (
        habits.habit_log,
        "Отметки привычек за период (date_from, date_to - YYYY-MM-DD, до 92 дней): date, "
        "habit_id, name, unit, done (1 - сделано, 0 - отмечено «нет»), amount (число или null), "
        "logged_at. "
        "Нет строки за день - не спрашивали. Отмечает пользователь командами coach habit "
        "done / undo.",
    ),
    "get_weekly_review": (
        review.weekly,
        "Недельный обзор: последние weeks ISO-недель (Пн-Вс, от 1 до 12, по умолчанию 4), от "
        "старой к новой, последняя - текущая неполная (partial). По неделе: tss, total (общая "
        "нагрузка), work_hours, evening_hours, weekend_work_hours, todo_closed, todo_open, mood, "
        "stress, sleep, readiness (средние, null - данных нет), days_with_data, delta - разница "
        "с предыдущей неделей (null - нет базы). Выводов нет - их делает тренер.",
    ),
    "get_agenda": (
        agenda.agenda,
        "События тренера в календаре (date_from, date_to - YYYY-MM-DD, до 92 дней): черновики "
        "(draft) и записанные в календарь (written) с днём начала в периоде, плюс активный "
        "повторяющийся чек-ин: id, kind (training/practice/rest/sleep/checkin/task), title, date, "
        "start_at, end_at, all_day, note, category (для нагрузки или null), alarm_min, repeat, "
        "workout_id, practice_id, status. Записывает в календарь пользователь командой "
        "coach event write.",
    ),
    "get_sport_nutrition": (
        tools.sport_nutrition,
        "Протоколы спортивного питания (kind=protocol: name, phase before/during/after, sport или "
        "null, min_duration_min, offset_min, carbs_g, protein_g, fluid_ml, sodium_mg - для "
        "during в час, note) или добавки (kind=supplement: name, dose, unit, schedule, time_note, "
        "note). Меняет пользователь командами coach protocol / coach supplement.",
    ),
    "get_sport_nutrition_for": (
        tools.sport_nutrition_for,
        "Питание к тренировкам дня (без отменённых): по каждой before / during / after, "
        "water_only (короче 75 минут - во время только вода), duration_unknown (длительности "
        "нет - спроси пользователя); supplements: daily всегда, остальные в день тренировки, "
        "taken - добавка за этот день уже принята. date - YYYY-MM-DD.",
    ),
    "get_supplement_log": (
        tools.supplement_log,
        "Журнал приёма добавок за период (date_from, date_to - YYYY-MM-DD, до 92 дней): id, "
        "item_id, name, date, taken_at, dose (null - по норме добавки), unit, note. "
        "Отмечает пользователь командами coach supplement take / untake.",
    ),
    "get_meds": (
        tools.meds,
        "Курсы витаминов, минералов, электролитов и безрецептурных средств: name, kind "
        "(vitamin/mineral/electrolyte/otc), dose, unit, schedule, time_note, start_date, "
        "end_date (null - бессрочно), note. date - YYYY-MM-DD: только курсы этого дня "
        "(training_day/before/after - только если в этот день есть тренировка); без date - "
        "все живые курсы, в т.ч. закончившиеся. "
        "Меняет пользователь командами coach med.",
    ),
    "get_food_pending": (
        tools.food_pending,
        "Записи еды без КБЖУ за все дни (для /coach-food).",
    ),
    "save_food_nutrition": (
        tools.save_food_nutrition,
        "Записать КБЖУ (kcal, protein_g, fat_g, carbs_g — на всю порцию записи) для записи "
        "еды без КБЖУ по food_id; посчитанные не меняет.",
    ),
    "create_draft_workout": (
        tools.create_draft_workout,
        "Записать тренировку плана черновиком (draft). sport: strength / mobility / run / "
        "bike / swim; date - YYYY-MM-DD; name - название; spec - объект, форма зависит от sport. "
        "Необязательно везде: estimated_duration_secs (секунды), у упражнения или шага "
        "title (название по-русски для телефона) и note (заметка). "
        'strength: {"exercises": [{"category": "BENCH_PRESS", "exercise": '
        '"BARBELL_BENCH_PRESS", "sets": 3, "reps": 8, "rest_seconds": 90, "weight_kg": 40, '
        '"title": "Жим лёжа"}]} - category и exercise обязательны, это коды каталога Garmin '
        "(SQUAT / BARBELL_BACK_SQUAT, ROW / BARBELL_ROW и т.п.); упражнение - sets подходов "
        "с отдыхом. "
        'mobility (растяжка): {"steps": [{"exercise": "STRETCH_CAT_COW", "seconds": 40, '
        '"description": "Техника по-русски, коротко", "title": "Кошка-корова"}]} - exercise '
        "обязателен, код STRETCH_* / WARM_UP_* каталога Garmin, description обязателен. "
        'run / bike / swim: {"steps": [{"type": "warmup", "seconds": 600}, {"type": '
        '"interval", "meters": 5000, "pace_sec_per_km": [360, 330], "note": "ровно"}, '
        '{"type": "cooldown", "seconds": 300}]} - type: warmup / interval / recovery / '
        "cooldown / rest; шаг - seconds или meters; pace_sec_per_km - [медленнее, быстрее], "
        "сек на км. Для телефона беговые шаги лучше задавать по времени (seconds).",
    ),
    "cancel_draft_workout": (
        tools.cancel_draft_workout,
        "Отменить черновик тренировки по id (только draft; утверждённые и отправленные нельзя).",
    ),
    "get_workout_link": (
        links.workout_link,
        "Ссылка на страницу-плеер с тренировкой плана по id (для телефона без часов; "
        "отменённые нельзя). time - HH:MM, необязательно, для календаря. "
        "Ответ: поля workout_id, name, date, url, length и картинка с QR-кодом ссылки. "
        "Покажи url пользователю как есть, не сокращай и не меняй; QR - отсканировать "
        "камерой телефона. Для телефона беговые шаги лучше по времени, а не по метрам. "
        "Ссылка длиннее 2000 символов - ошибка: сократи "
        "заметки и названия или раздели тренировку.",
    ),
    "create_draft_event": (
        agenda.create_draft_event,
        "Записать событие календаря черновиком (draft). kind: training / practice / rest / sleep / "
        "checkin / task; title - название; start_at, end_at - местное время YYYY-MM-DDTHH:MM "
        "(день начала от 30 дней назад до 14 вперёд, не длиннее 24 часов). category "
        "(work / personal / hobby / rest) - как событие считается в нагрузке: у rest и sleep по "
        "умолчанию rest, у task задавай явно, у training / practice / checkin не задаётся. "
        "alarm_min - за сколько минут напомнить; repeat=daily - только у checkin, один на всех; "
        "workout_id / practice_id - связь с тренировкой плана или практикой; note - заметка; "
        "all_day - на весь день. Ответ: draft_id. В календарь кладёт пользователь командой "
        "coach event write.",
    ),
    "cancel_draft_event": (
        agenda.cancel_draft_event,
        "Отменить черновик события календаря по id (только draft; записанные в календарь нельзя).",
    ),
    "propose_phase": (tools.propose_phase, "Предложить фазу (proposed); принимает пользователь."),
}


def bind(func: Callable[..., Any], db_path: str | Path | None) -> Callable[..., Any]:
    """Инструмент без параметра conn: базу открывает на один вызов (путь: аргумент,
    $AI_COACH_DB). MCP строит схему аргументов по сигнатуре, а у tool она (*args, **kwargs),
    поэтому __signature__ копируется из func без первого параметра conn."""

    def tool(*args: Any, **kwargs: Any) -> Any:
        conn = open_db(db_path)
        try:
            return func(conn, *args, **kwargs)
        finally:
            conn.close()

    signature = inspect.signature(func)
    tool.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=list(signature.parameters.values())[1:]
    )
    return tool


def build_server(db_path: str | Path | None = None) -> MCPServer:
    server = MCPServer("ai-coach", instructions=INSTRUCTIONS)
    for name, (func, description) in TOOLS.items():
        server.add_tool(bind(func, db_path), name=name, description=description)
    return server


def main() -> None:
    build_server().run("stdio")

-- События тренера в календаре: черновик (draft) -> записано (written) в календарь коуча -> снято (removed)
-- или отменён черновик (cancelled). kind: training, practice, rest, sleep, checkin, task.
-- Время местное без пояса, date - день начала. category (work/personal/hobby/rest) - для нагрузки,
-- NULL - в нагрузку не входит. alarm_min - за сколько минут напомнить. repeat - только ежедневный
-- checkin. calendar_uid - eventIdentifier из календаря (у повторяющегося один на все вхождения).
-- removed_by: cli - снято командой, calendar - пропало из календаря само (sync).
-- workout_id и practice_id - связь без внешнего ключа: живость проверяет service.
CREATE TABLE coach_events (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('training', 'practice', 'rest', 'sleep', 'checkin', 'task')),
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0 CHECK (all_day IN (0, 1)),
    note TEXT,
    category TEXT CHECK (category IN ('work', 'personal', 'hobby', 'rest')),
    alarm_min INTEGER CHECK (alarm_min >= 0),
    repeat TEXT CHECK (repeat IS NULL OR (repeat = 'daily' AND kind = 'checkin')),
    workout_id INTEGER,
    practice_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'written', 'cancelled', 'removed')),
    calendar_uid TEXT,
    created_at TEXT NOT NULL,
    written_at TEXT,
    removed_at TEXT,
    removed_by TEXT CHECK (removed_by IN ('cli', 'calendar'))
);
CREATE INDEX coach_events_date ON coach_events (date);
CREATE INDEX coach_events_status ON coach_events (status);
CREATE INDEX coach_events_uid ON coach_events (calendar_uid);

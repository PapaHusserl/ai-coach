-- Очередь решений на будущее: слова от тренера (text), черновики тренировок (workout) и фазы (phase).
-- ref_id - id planned_workouts или phases, связь без внешнего ключа (объекты в двух таблицах), на объект
-- один пункт. Строки не удаляются. result и result_at - исполнение решения словами (только status = yes).
CREATE TABLE decision_log (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL CHECK (length(trim(text)) > 0),
    kind TEXT NOT NULL DEFAULT 'text' CHECK (kind IN ('text', 'workout', 'phase')),
    ref_id INTEGER,
    target_date TEXT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'yes', 'no', 'dropped')),
    decided_at TEXT,
    result TEXT CHECK (result IS NULL OR (result IN ('kept', 'missed') AND status = 'yes')),
    result_at TEXT,
    CHECK ((kind = 'text') = (ref_id IS NULL))
);
CREATE UNIQUE INDEX decision_log_object ON decision_log (kind, ref_id) WHERE ref_id IS NOT NULL;
CREATE INDEX decision_log_status ON decision_log (status);

-- Открытое на момент миграции: черновики с датой не раньше сегодня и предложенные фазы.
INSERT INTO decision_log (text, kind, ref_id, target_date, created_at)
SELECT name, 'workout', id, date, created_at FROM planned_workouts
WHERE status = 'draft' AND date >= date('now', 'localtime');

INSERT INTO decision_log (text, kind, ref_id, target_date, created_at)
SELECT name, 'phase', id, start_date, created_at FROM phases WHERE status = 'proposed';

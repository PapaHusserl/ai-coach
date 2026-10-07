-- Курсы витаминов, минералов, электролитов и безрецептурных средств. Рецептурного нет.
-- Удаление - пометка deleted_at (NULL - живая строка). Имя уникально среди живых без учёта
-- регистра: это проверяет Python (SQLite не понижает кириллицу), индекс - страховка от точного дубля.
-- schedule как у supplement: daily - каждый день, остальные - в день тренировки.
-- end_date NULL - курс бессрочный; даты YYYY-MM-DD.
CREATE TABLE med_course (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('vitamin', 'mineral', 'electrolyte', 'otc')),
    dose REAL NOT NULL CHECK (dose > 0),
    unit TEXT NOT NULL CHECK (unit IN ('mg', 'mcg', 'iu', 'g', 'ml', 'pcs')),
    schedule TEXT NOT NULL CHECK (schedule IN ('daily', 'training_day', 'before', 'after')),
    time_note TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    CHECK (end_date IS NULL OR end_date >= start_date)
);
CREATE UNIQUE INDEX med_course_name_alive ON med_course (name) WHERE deleted_at IS NULL;

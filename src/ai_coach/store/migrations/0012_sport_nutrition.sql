-- Протоколы спортивного питания и добавки. Удаление - пометка deleted_at (NULL - живая строка).
-- Имя уникально среди живых без учёта регистра: это проверяет Python (SQLite не понижает
-- кириллицу), индекс - страховка от точного дубля.
-- phase: before | during | after; sport NULL - для любого вида. offset_min - за сколько минут
-- до начала (before) или через сколько после конца (after). Количества - разово, для during - в час.
CREATE TABLE nutrition_protocol (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN ('before', 'during', 'after')),
    sport TEXT CHECK (sport IN ('strength', 'mobility', 'run', 'bike', 'swim')),
    min_duration_min INTEGER NOT NULL DEFAULT 0 CHECK (min_duration_min >= 0),
    offset_min INTEGER NOT NULL DEFAULT 0 CHECK (offset_min >= 0),
    carbs_g REAL NOT NULL DEFAULT 0 CHECK (carbs_g >= 0),
    protein_g REAL NOT NULL DEFAULT 0 CHECK (protein_g >= 0),
    fluid_ml REAL NOT NULL DEFAULT 0 CHECK (fluid_ml >= 0),
    sodium_mg REAL NOT NULL DEFAULT 0 CHECK (sodium_mg >= 0),
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE UNIQUE INDEX nutrition_protocol_name_alive ON nutrition_protocol (name)
    WHERE deleted_at IS NULL;

-- Добавки: доза и график приёма (daily - каждый день, остальные - в день тренировки).
CREATE TABLE supplement (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    dose REAL NOT NULL CHECK (dose > 0),
    unit TEXT NOT NULL CHECK (unit IN ('g', 'mg', 'ml', 'pcs')),
    schedule TEXT NOT NULL CHECK (schedule IN ('daily', 'training_day', 'before', 'after')),
    time_note TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE UNIQUE INDEX supplement_name_alive ON supplement (name) WHERE deleted_at IS NULL;

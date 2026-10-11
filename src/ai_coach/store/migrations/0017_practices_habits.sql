-- Практики восстановления (как recipe): kind - дыхание, пауза, прогулка, сон; minutes - длительность (NULL - не задана);
-- trigger - когда применять; steps - шаги текстом. Удаление - пометка deleted_at.
CREATE TABLE practice (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('breathing', 'pause', 'walk', 'sleep')),
    minutes INTEGER CHECK (minutes > 0),
    trigger TEXT,
    steps TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE UNIQUE INDEX practice_name_alive ON practice (name) WHERE deleted_at IS NULL;

-- Привычки: да/нет за день и необязательное число (unit - единица числа, NULL - без числа).
CREATE TABLE habit (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    unit TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE UNIQUE INDEX habit_name_alive ON habit (name) WHERE deleted_at IS NULL;

-- Отметка привычки за день: одна на дату и привычку, done 0/1, amount - число (может быть NULL).
CREATE TABLE habit_log (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    habit_id INTEGER NOT NULL REFERENCES habit (id),
    done INTEGER NOT NULL CHECK (done IN (0, 1)),
    amount REAL CHECK (amount >= 0),
    logged_at TEXT,
    UNIQUE (date, habit_id)
);

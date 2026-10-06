-- Начальная схема. Даты и время — ISO-строки. raw_json — ответ Garmin как есть.

CREATE TABLE daily_metrics (
    date TEXT PRIMARY KEY,
    sleep_seconds INTEGER,
    sleep_score INTEGER,
    hrv_last_night INTEGER,
    hrv_weekly_avg INTEGER,
    hrv_status TEXT,
    body_battery_charged INTEGER,
    body_battery_drained INTEGER,
    stress_avg INTEGER,
    readiness_score INTEGER,
    readiness_level TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE activities (
    activity_id INTEGER PRIMARY KEY,
    start_time_local TEXT NOT NULL,
    start_time_gmt TEXT,
    type_key TEXT NOT NULL,
    name TEXT,
    duration_s REAL,
    distance_m REAL,
    calories REAL,
    avg_hr REAL,
    max_hr REAL,
    training_load REAL,
    workout_id INTEGER,
    raw_json TEXT NOT NULL
);
CREATE INDEX activities_start ON activities (start_time_local);

CREATE TABLE strength_sets (
    id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL REFERENCES activities (activity_id) ON DELETE CASCADE,
    set_index INTEGER NOT NULL,
    wkt_step_index INTEGER,
    exercise_category TEXT,
    exercise_name TEXT,
    reps INTEGER,
    weight REAL,
    duration_s REAL,
    set_type TEXT,
    start_time TEXT,
    raw_json TEXT NOT NULL,
    UNIQUE (activity_id, set_index)
);

CREATE TABLE weight_log (
    id INTEGER PRIMARY KEY,
    measured_at TEXT NOT NULL,
    weight_kg REAL NOT NULL
);

CREATE TABLE goals (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    target TEXT,
    target_date TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE phases (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'accepted')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    accepted_at TEXT
);

CREATE TABLE goal_events (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER NOT NULL REFERENCES goals (id),
    event_type TEXT NOT NULL,
    payload_json TEXT,
    occurred_at TEXT NOT NULL
);
CREATE INDEX goal_events_goal ON goal_events (goal_id, occurred_at);

CREATE TABLE planned_workouts (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    sport TEXT NOT NULL CHECK (sport IN ('strength', 'mobility', 'run', 'bike', 'swim')),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'pushed', 'cancelled')),
    workout_json TEXT NOT NULL,
    garmin_workout_id INTEGER,
    garmin_schedule_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    pushed_at TEXT
);
CREATE INDEX planned_workouts_date ON planned_workouts (date);

CREATE TABLE plan_actual (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    planned_id INTEGER REFERENCES planned_workouts (id),
    activity_id INTEGER REFERENCES activities (activity_id),
    kind TEXT NOT NULL CHECK (kind IN ('done', 'skipped', 'extra', 'different')),
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK (
        (kind IN ('done', 'different') AND planned_id IS NOT NULL AND activity_id IS NOT NULL)
        OR (kind = 'skipped' AND planned_id IS NOT NULL AND activity_id IS NULL)
        OR (kind = 'extra' AND planned_id IS NULL AND activity_id IS NOT NULL)
    )
);
CREATE INDEX plan_actual_date ON plan_actual (date);

CREATE TABLE food_log (
    id INTEGER PRIMARY KEY,
    logged_at TEXT NOT NULL,
    text TEXT NOT NULL,
    kcal REAL,
    protein_g REAL,
    fat_g REAL,
    carbs_g REAL
);

CREATE TABLE sync_log (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT
);

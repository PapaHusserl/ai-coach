-- Группы продуктов записи еды (разнообразие, шаг 24): оценка тренера при расчёте КБЖУ.
-- Группа - множество на запись, поэтому отдельная таблица; словарь ключей - в CHECK
-- (должен совпадать с FOOD_GROUPS в nutrition/groups.py). Записи до шага остаются без групп.
CREATE TABLE food_group (
    food_id INTEGER NOT NULL REFERENCES food_log (id),
    group_key TEXT NOT NULL CHECK (
        group_key IN (
            'fish', 'red_meat', 'poultry', 'eggs', 'dairy', 'legumes',
            'nuts_seeds', 'greens', 'vegetables', 'fruit_berries', 'whole_grains'
        )
    ),
    PRIMARY KEY (food_id, group_key)
);

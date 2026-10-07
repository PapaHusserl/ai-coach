-- Справочник рецептов: КБЖУ на 100 г готового блюда, yield_g - вес готового (NULL - неизвестен).
-- Удаление - пометка deleted_at (NULL - живой рецепт). Имя уникально среди живых без учёта
-- регистра: это проверяет Python (SQLite не понижает кириллицу), индекс - страховка от
-- точного дубля.
CREATE TABLE recipe (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kcal_100 REAL NOT NULL CHECK (kcal_100 >= 0 AND kcal_100 <= 900),
    protein_100 REAL NOT NULL CHECK (protein_100 >= 0),
    fat_100 REAL NOT NULL CHECK (fat_100 >= 0),
    carbs_100 REAL NOT NULL CHECK (carbs_100 >= 0),
    yield_g REAL CHECK (yield_g > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE UNIQUE INDEX recipe_name_alive ON recipe (name) WHERE deleted_at IS NULL;

-- Состав рецепта: продукты как в кладовой (g/ml/pcs).
CREATE TABLE recipe_ingredient (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipe (id),
    product TEXT NOT NULL,
    qty REAL NOT NULL CHECK (qty > 0),
    unit TEXT NOT NULL CHECK (unit IN ('g', 'ml', 'pcs'))
);
CREATE INDEX recipe_ingredient_recipe ON recipe_ingredient (recipe_id);

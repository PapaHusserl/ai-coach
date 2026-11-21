-- Вечерний чек-ин: усталость и раздражительность за день 1-5 (NULL - не спрашивали).
ALTER TABLE wellbeing_log ADD COLUMN fatigue INTEGER CHECK (fatigue BETWEEN 1 AND 5);
ALTER TABLE wellbeing_log ADD COLUMN irritability INTEGER CHECK (irritability BETWEEN 1 AND 5);

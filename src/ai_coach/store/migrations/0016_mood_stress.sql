-- Вечерний чек-ин: настроение и стресс 1-5 в записи самочувствия (NULL - не спрашивали).
ALTER TABLE wellbeing_log ADD COLUMN mood INTEGER CHECK (mood BETWEEN 1 AND 5);
ALTER TABLE wellbeing_log ADD COLUMN stress INTEGER CHECK (stress BETWEEN 1 AND 5);

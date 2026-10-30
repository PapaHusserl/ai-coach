-- Вечерний чек-ин: мысли о работе, помехи и ценность дня 1-5, погружение 0/1 (NULL - не спрашивали).
ALTER TABLE wellbeing_log ADD COLUMN work_thoughts INTEGER CHECK (work_thoughts BETWEEN 1 AND 5);
ALTER TABLE wellbeing_log ADD COLUMN hindrance INTEGER CHECK (hindrance BETWEEN 1 AND 5);
ALTER TABLE wellbeing_log ADD COLUMN valuable INTEGER CHECK (valuable BETWEEN 1 AND 5);
ALTER TABLE wellbeing_log ADD COLUMN flow INTEGER CHECK (flow IN (0, 1));

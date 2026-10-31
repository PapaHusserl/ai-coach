-- Вызов/помеха (JD-R) для рабочих событий календаря; NULL - не рабочее или старая запись.
ALTER TABLE calendar_events ADD COLUMN demand TEXT CHECK (demand IN ('challenge', 'hindrance'));

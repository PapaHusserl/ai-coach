-- Опросник чек-ина: имя готового набора вопросов (evening, feel, focus, none). NULL - старый чек-ин
-- (анкета вечера) или не чек-ин. Белый список значений - в коде (agenda/service.py), не в CHECK.
ALTER TABLE coach_events ADD COLUMN survey TEXT;

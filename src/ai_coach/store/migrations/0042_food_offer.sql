-- Запись еды из варианта блюда: offer_id - вариант meal_offer, связь без внешнего ключа (варианты
-- заменяются и удаляются); NULL - запись «своё» или из CLI.
ALTER TABLE food_log ADD COLUMN offer_id INTEGER;

# Ресёрч: погода и самочувствие (метеочувствительность)

Дата: 2026-11-22, научный ресерчер, заход. Шаг — docs/plan-p7.md, развилка Р26 (1); пункт — BACKLOG 147. Пересказы
статей — вне репо, `~/projects/nauchnyi-resercher/vygruzki/ai-coach-weather-wellbeing/papers/`, тексты —
`papers/raw/`, ответы о ретракциях — `papers/retraction/`; пометки `papers/<файл>` ниже — относительно
`~/projects/nauchnyi-resercher/vygruzki/ai-coach-weather-wellbeing/`. Личных данных
в документе нет. Решений здесь нет: выводы для прогноза пишет шаг.

## Вопрос

Какие факторы погоды связаны с самочувствием и насколько это доказано; пороги и окно перепада давления; давление на
уровне моря или на высоте места; сколько личных наблюдений нужно для подстройки порога; не ухудшает ли самочувствие
само предупреждение; откуда цифра «≥ 6–10 гПа/сутки».

## Главное

- Почти все данные — о мигрени, головной боли и хронической боли у больных; о «самочувствии» здорового человека
  (тошнота, тяжёлая голова) прямых данных в найденном нет (запросы — в конце). Всё ниже — перенос из этих групп.
- Связь давления и температуры с мигренью в мета-анализе есть, но слабая; на уровне группы при артрите — около нуля.
  `[набл]`
- Чувствительность к погоде — индивидуальная и разнонаправленная: у меньшинства людей есть, у большинства нет.
  `[набл]`
- Проверенного порога и окна для прогноза нет. Цифра «6–10 hPa» в литературе есть (Okuma 2015), но это отклонение
  уровня давления от 1013, а не перепад за сутки.

## Факторы погоды

- **Давление.** МА по мигрени: «ambient pressure (OR = 1.07, 95% CI = 1.01-1.15)» [проверено: А,
  papers/2025-migraine-weather-ma.md]. Систематический обзор по перепадам: «Findings were inconsistent», методы
  измерения перепада «varied substantially» (papers/2025-pressure-migraine-sr.md). Хроническая боль:
  «OR of 0.962 (0.937–0.987) per 10-mbar increase» [проверено: П, papers/2019-dixon-cloudy.md] — ниже давление,
  чаще скачок боли. Неотложная помощь при головной боли: «OR 0.939 per 5 mm Hg» [проверено: П,
  papers/2009-mukamal-headache.md] — только не-мигрень, «in the 48 to 72 hours before hospitalization» [проверено: П, papers/2009-mukamal-headache.md]. Артрит: боли — нет связи
  (papers/2026-ra-weather-ma.md, papers/2011-smedslund-rain-pain.md). `[набл]`
- **Температура.** Мигрень: «temperature (OR = 1.15, 95% CI = 1.02-1.29)» [проверено: А,
  papers/2025-migraine-weather-ma.md]. Тяжёлая головная боль: «odds ratio [OR] for a 5°C increment 1.075»
  [проверено: П, papers/2009-mukamal-headache.md]. Хроническая боль — не значимо: «OR 0.996 (0.985–1.007) per 1 °C
  increase» [проверено: П, papers/2019-dixon-cloudy.md]. Настроение: температура связана с негативным аффектом,
  эффект «only small» (papers/2008-denissen-mood.md). `[набл]`
- **Влажность.** Мигрень — нет: «humidity (OR = 1.04, 95% CI = 0.97-1.11)» [проверено: А,
  papers/2025-migraine-weather-ma.md]. Хроническая боль — сильнейший из четырёх: «OR of 1.139 (95% confidence interval
  1.099–1.181) per 10 percentage point increase» [проверено: П, papers/2019-dixon-cloudy.md]. Головная боль по
  приложению — связь с высокой влажностью (papers/2023-katsuki-app.md). `[набл]`
- **Ветер.** Хроническая боль: «OR of 1.02 (1.005–1.035) per 1 m s -1 increase» [проверено: П,
  papers/2019-dixon-cloudy.md]; настроение — связь с негативным аффектом (papers/2008-denissen-mood.md). `[набл]`
- **Суммарно.** «the ‘worst’ combination of weather variables would increase the odds of a pain event by just over
  20% compared to an average day» [проверено: П, papers/2019-dixon-cloudy.md].
- **Геомагнитные бури.** Только нарративный обзор: «Moderate evidence; significant correlations noted but require
  causal analysis»; исследования «inherently limited by their inability to establish causality»
  (papers/2026-geomagnetic-review.md). `[мнение]`

## Пороги и окно

- **Сутки, падение.** Мигрень, дневник за год: частота выше, когда давление со дня приступа на следующий день
  «was lower by more than 5 hPa» [проверено: А, papers/2011-kimoto-pressure.md]; связь у «18 (64%) patients»
  из «28 migraine patients» [проверено: А, papers/2011-kimoto-pressure.md] [проверено: А, papers/2011-kimoto-pressure.md]. `[набл]`
- **Сутки, оба направления.** Онтарио, суточный перепад («subtracting the previous day’s pressure from the current day’s»): начало
  мигрени связано с «positive and negative changes in barometric pressure», сильнее всего в тот же день;
  межквартильный размах перепада «942.3 Pa» [проверено: П, papers/2026-migraine-case-time-series.md]; связь
  нелинейная, порога в гПа нет. `[набл]`
- **6 часов.** Почасовые записи приложения: «a significant decrease in barometric pressure 6 h before (p < 0.001,
  gain = 11.7)» [проверено: А, papers/2023-katsuki-app.md]; величины падения в абстракте нет. `[набл]`
- **3 часа.** Не нашёл исследований с окном 3 ч (запросы — в конце).
- **Скорость падения у животных.** Крысы с невропатией: «rates of decompression ≥5 hPa/h and ≥10 hPa/h and
  magnitudes of decompression ≥5 hPa and ≥10 hPa augmented pain-related behaviors» [проверено: А,
  papers/2011-sato-rats.md]. `[жив/in vitro]`
- **Прогноз «заранее».** При фибромиалгии «No weather parameter predicted change in the subsequent pain measures»
  (papers/2014-smedslund-fibromyalgia.md). `[набл]`

## Давление: уровень моря или высота места

- В найденных работах это не сравнивалось. Houle 2013 брал «median station pressure» (давление станции,
  papers/2013-houle-natural-experimentation.md); Okuma 2015 сравнивал с «standard atmospheric pressure ... 1013 hPa»
  [проверено: П, papers/2015-okuma-fluctuations.md] — то есть с давлением на уровне моря.
- Для перепада за часы в одной точке приведённое к уровню моря и станционное давление меняются почти одинаково;
  для сравнения уровня с «1013» нужно давление на уровне моря [не проверено: память].

## Сколько личных наблюдений (n-of-1)

- Числа «нужно N дней» в найденном нет (запросы — в конце).
- Простое сравнение «похожих» дней почти не работает: «Fluctuations in weather patterns resulted in a median of 2.3
  days each year that were similar» [проверено: П, papers/2013-houle-natural-experimentation.md]; при многих
  предикторах похожий день находится «once in approximately 684 days, 26 days, or 4 days» в зависимости от порога
  сходства [проверено: П, papers/2013-houle-natural-experimentation.md]. Авторы советуют формальный эксперимент или
  статистическое выравнивание (регрессию). `[набл]`
- Доля чувствительных мала и направление разное: «1 in 10 patients with chronic pain were sensitive to the
  temperature, 1 in 25 to relative humidity, 1 in 50 to pressure» [проверено: П,
  papers/2022-schultz-heterogeneity.md], по ежедневным записям до «15 months» [проверено: П, papers/2022-schultz-heterogeneity.md]. `[набл]`
- Индивидуальные различия во влиянии погоды на настроение есть и не объясняются полом, возрастом и чертами личности
  (papers/2008-denissen-mood.md). `[набл]`

## Ноцебо: вредит ли предупреждение

- Прямых исследований предупреждений о погоде не нашёл (запросы — в конце).
- Перенос из экологического риска (инфразвук ветряков): после медиа-предупреждений участники «reported increased
  symptoms and mood deterioration from baseline»; объяснение ноцебо вернуло симптомы к исходным (papers/
  2015-crichton-wind-nocebo.md). `[РКИ]` (лабораторный: «Sixty-six volunteers were randomly
  assigned» [проверено: А, papers/2015-crichton-wind-nocebo.md])
- Перенос из клиники: «Individuals with long-term conditions can show strong nocebo responses across a range of
  symptoms» (papers/2026-nocebo-sr.md, «Thirteen studies» [проверено: П, papers/2026-nocebo-sr.md]).
- Убеждение искажает самооценку связи: «prior belief about the potency of a trigger ... accounting for 17% of the
  total variation» [проверено: П, papers/2023-learning-triggers.md]. `[набл]`
- Против: при фибромиалгии психологические переменные связь погоды и боли не меняли
  (papers/2014-smedslund-fibromyalgia.md).

## Откуда «≥ 6–10 гПа/сутки»

- Ближайший источник с этими числами — Okuma 2015: «Small decreases of 6–10 hPa relative to the standard atmospheric
  pressure of 1013 hPa induced migraine attacks most frequently» [проверено: П, papers/2015-okuma-fluctuations.md];
  приступы — при давлении «within 1003–1007 hPa» [проверено: П, papers/2015-okuma-fluctuations.md].
- Это не перепад за сутки, а отклонение уровня от 1013; работа — «34 patients with migraine» [проверено: П,
  papers/2015-okuma-fluctuations.md], один тайфун, без контроля. `[набл]`
- Суточное окно с близким числом — Kimoto 2011, «more than 5 hPa» [проверено: А, papers/2011-kimoto-pressure.md].
- Вывод ресерчера: формулировка «≥ 6–10 гПа/сутки» в найденном не встречается; вероятно, это смешение порога
  уровня (Okuma) с суточным перепадом (Kimoto) — предположение, источника не нашёл.

## Вывод авторов и вывод ресерчера

- Авторы: погода — значимый триггер мигрени (Li 2025), связь «modest» при хронической боли (Dixon 2019), у
  чувствительных — разного направления (Schultz 2022); геомагнитные эффекты требуют причинного анализа.
- Ресерчер: эффекты небольшие и неоднородные; порог для прогноза литература не даёт — ни величины, ни окна;
  личная подстройка по дневнику требует длинного ряда и модели с поправками; предупреждение может само усиливать
  жалобы (перенос, прямых данных нет). Сила — `[набл]`, ноцебо — перенос из `[РКИ]` вне погоды.

## Не нашёл — запросы этого захода (PubMed esearch, 2026-11-22)

- `weather AND (pain OR headache OR migraine) AND (systematic[sb] OR meta-analysis[pt])`
- `(meteorosensitivity OR meteoropathy OR weather sensitivity)`; `meteorosensitivity[tiab] OR meteoropathy[tiab]`
- `barometric pressure AND migraine`; `"10 hPa" AND (headache OR pain)`; `"6 hPa" AND (headache OR pain)` (0)
- `geomagnetic AND (health OR well-being) AND (systematic[sb] OR review[pt])`;
  `geomagnetic storm AND (mood OR wellbeing OR symptoms) AND review[pt]`
- `headache triggers AND natural experimentation`; `meteorosensitivity AND (n-of-1 OR single-case)` (0)
- `weather AND nocebo`; `weather warning AND nocebo`; `weather[ti] AND (expectation[tiab] OR nocebo[tiab] OR
  belief[tiab]) AND symptom*`; `nocebo AND (warning OR forecast OR information) AND symptoms AND (systematic[sb])`
- `weather beliefs AND pain AND (expectation OR belief)`

Не искал: Cochrane по `[jour]`, Europe PMC, Crossref вне PubMed; высотная болезнь и перелёты (другая область);
опросники METEO-Q и распространённость метеочувствительности.

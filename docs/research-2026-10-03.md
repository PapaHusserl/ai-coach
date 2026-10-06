# Ресёрч рынка (дядя-кабан, 2026-10-03)

## Коммерческие продукты
| Проект | Что | Чего не хватает |
|---|---|---|
| Garmin Connect+ ($6.99/мес, $70/год) | С янв 2026 дневник питания (штрихкод, фото) + AI-инсайты питание↔сон | Нет тренера/плана под несколько целей, слабая силовая, нет CLI и открытых данных |
| HumanGO | AI-планировщик триатлон/мультиспорт, синк с Garmin | Силовая вторична, нет питания/композиции тела |
| HybridX (hybridx.app) | Гибрид сила+выносливость, чат-тренер, план на Garmin/COROS | Питание и разбор сна не заявлены |
| LiftTrack (июнь 2026) | AI-силовые для Garmin | Только силовая |
| AI Endurance, Athletica, TriDot, TrainingPeaks, Runna | Выносливость | Нет силовой как цели, нет питания |

## Open-source (звёзды на 2026-10-03)
- **Taxuspt/garmin_mcp** — MCP-сервер Garmin Connect, ~1281★, живой. Данных достаточно, тренерской логики нет.
- **leonzzz435/garmin-ai-coach** — мультиагентный тренер выносливости, 152★, затих с 2026-01, вероятно сломан после марта 2026 (не проверено).
- **awalderhaugjohnsen/athlete-management-system** — LangGraph, гибрид+питание+восстановление, перепланирование, загрузка на часы. Почти наша идея, но 1★. Стоит прочитать код.
- **nrvim/garmin-givemydata** — Garmin → SQLite + MCP, 155★.
- Мелкие беговые MCP-тренеры: jorgenjanssonlee/garmin-training-coach, Bartolome69/garmin-mcp, kavakoss/mcp-garmin-connect.

## Доступ к данным Garmin
- Официальный API частным лицам закрыт (только юрлица, приём заявок на паузе).
- Март 2026: Garmin усилил Cloudflare/TLS fingerprinting → **garth DEPRECATED** (с 27.03.2026).
- **python-garminconnect ≥0.3.0** работает (curl_cffi, имитация Android TLS), 3082★, живой. Токены garth в 0.3 не читаются.
- **GarminDB** — выгрузка в SQLite, 3326★, живой.
- Риск: следующий шаг Garmin против ботов снова сломает доступ → обязателен локальный кэш.

## Питание
- Connect+ Nutrition — нужна подписка (у пользователя нет).
- MyFitnessPal — API только партнёрам; есть неофициальная python-myfitnesspal.
- Cronometer — публичного API нет (CSV, неофициальный cronometer_mcp).
- Решение-кандидат: собственный лог свободным текстом с LLM-разбором в КБЖУ.

## Вердикт
Собирать из готовых кусков: слой данных готов, строить свой «тренерский» слой (цели, план, план/факт, питание, недельный разбор). Свободная ниша: несколько целей + план/факт с памятью + разбор питания вместе со сном/HRV + терминал.

## Риски
- Хрупкая неофициальная авторизация Garmin.
- Нет API питания.
- Качество рекомендаций без явной модели нагрузки (CTL/ATL, прогрессия).
- Стоимость токенов при ежедневном анализе.

## Ссылки
- https://github.com/Taxuspt/garmin_mcp
- https://github.com/cyberjunky/python-garminconnect
- https://github.com/tcgoetz/GarminDB
- https://github.com/matin/garth
- https://github.com/awalderhaugjohnsen/athlete-management-system
- https://github.com/leonzzz435/garmin-ai-coach
- https://github.com/nrvim/garmin-givemydata
- https://www.hybridx.app/
- https://humango.ai/app
- https://www.dcrainmaker.com/2026/01/garmin-connect-nutrition-logging-connect.html

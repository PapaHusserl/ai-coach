# 127. DOM-код форм пульта без юнит-тестов
status: done
priority: low
updated: 2026-11-26

Находка архитектора при закрытии П12 (docs/plan-p12.md, «Открыто: стенд», партия 3; риск 8): отсев вкладки формы
в `marks.js`, `tabFields`, `tabReady` юнит-тестами не покрыты. Смежно с BACKLOG 113.

## Закрыто

Шаг Н48, 2026-11-26 — docs/plan-n48.md; тесты DOM форм — `tests/web/marks-forms.test.mjs`, `tests/web/forms.test.mjs`.

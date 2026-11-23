-- Очередь отчётов тренера о проблемах системы: технический агент читает её, переписывает отчёт в пункт
-- BACKLOG и закрывает с номером пункта (backlog). Строки не удаляются.
CREATE TABLE system_report (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL CHECK (length(trim(text)) > 0),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'dropped')),
    closed_at TEXT,
    backlog INTEGER
);
CREATE INDEX system_report_status ON system_report (status);

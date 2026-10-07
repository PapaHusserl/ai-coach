# Проверки качества. Всё через uv; qlty — внешний бинарник (curl -fsSL https://qlty.sh | sh).
QLTY ?= $(shell command -v qlty 2>/dev/null || echo $(HOME)/.qlty/bin/qlty)
SMELLS_MAX ?= 0
# Модули для мутаций: по умолчанию изменённые относительно HEAD, иначе весь пакет.
MOD ?= $(or $(shell git diff --name-only HEAD -- src/ai_coach | grep '\.py$$' | sed -e 's|^src/||' -e 's|/__init__\.py$$||' -e 's|\.py$$||' -e 's|/|.|g' -e 's|$$|.*|'),ai_coach.*)

.PHONY: check lint fmt types smells dead cov mutate mutate-report install-trener

check: lint types smells dead cov
	@echo "check: OK"

lint:
	uv run ruff check
	uv run ruff format --check

fmt:
	uv run ruff format
	uv run ruff check --fix

types:
	uv run pyright

smells:
	@n=$$($(QLTY) smells --all --no-snippets 2>/dev/null | grep -cE '^ +[0-9]+  ' || true); \
	echo "smells: $$n (max $(SMELLS_MAX))"; \
	if [ $$n -gt $(SMELLS_MAX) ]; then $(QLTY) smells --all; exit 1; fi

dead:
	uv run vulture

cov:
	uv run pytest --cov

# Мутации: запускать фоном вне агента. Отчёт — reports/mutmut.txt.
mutate:
	@mkdir -p reports
	@echo "mutmut: $(MOD) -> reports/mutmut.log, отчёт reports/mutmut.txt"
	nohup sh -c 'uv run mutmut run "$(MOD)" > reports/mutmut.log 2>&1; $(MAKE) mutate-report' >/dev/null 2>&1 &

mutate-report:
	@mkdir -p reports
	uv run mutmut results --all true > reports/mutmut.txt 2>&1 || true
	@echo "отчёт: reports/mutmut.txt"; awk -F': ' 'NF==2{c[$$2]++} END{for(k in c) printf "  %s: %d\n", k, c[k]}' reports/mutmut.txt

# Команда `тренер` в любой папке: symlink в ~/.local/bin.
install-trener:
	mkdir -p $(HOME)/.local/bin
	ln -sf $(CURDIR)/bin/trener $(HOME)/.local/bin/тренер

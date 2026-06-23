CONFIG ?= runner/conversion_config.toml
SOURCES = conversion-engine/ assets/ runner/ tests/

# Read PYTHON_BIN from .env (same variable used by all conversion scripts).
# Falls back to python3 if .env is absent or PYTHON_BIN is unset.
PYTHON_BIN := $(shell grep -E '^PYTHON_BIN=' .env 2>/dev/null | cut -d= -f2- | tr -d '[:space:]')
ifeq ($(PYTHON_BIN),)
PYTHON_BIN := python3
endif

.PHONY: lint fmt typecheck test check convert

lint:
	ruff check $(SOURCES)

fmt:
	ruff format $(SOURCES)
	ruff check --fix $(SOURCES)

typecheck:
	basedpyright --pythonpath $(PYTHON_BIN) conversion-engine/ runner/

test:
	$(PYTHON_BIN) -m pytest tests/

check: lint typecheck test

convert:
	$(PYTHON_BIN) runner/batch_runner.py $(CONFIG)

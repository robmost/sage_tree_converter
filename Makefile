PYTHON ?= python3
CONFIG ?= runner/conversion_config.toml
SOURCES = conversion-engine/ assets/ runner/

.PHONY: lint fmt typecheck check convert

lint:
	ruff check $(SOURCES)

fmt:
	ruff format $(SOURCES)
	ruff check --fix $(SOURCES)

typecheck:
	basedpyright conversion-engine/ runner/

check: lint typecheck

convert:
	$(PYTHON) runner/batch_runner.py $(CONFIG)

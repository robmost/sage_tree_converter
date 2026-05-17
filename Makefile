PYTHON ?= python3
CONFIG ?= cli/conversion_config.toml
SOURCES = conversion-engine/ assets/ cli/

.PHONY: lint fmt typecheck check convert

lint:
	ruff check $(SOURCES)

fmt:
	ruff format $(SOURCES)
	ruff check --fix $(SOURCES)

typecheck:
	basedpyright conversion-engine/ cli/

check: lint typecheck

convert:
	$(PYTHON) cli/batch_runner.py $(CONFIG)

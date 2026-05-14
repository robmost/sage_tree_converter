PYTHON ?= python3
SOURCES = conversion-engine/ assets/

.PHONY: lint fmt typecheck check

lint:
	ruff check $(SOURCES)

fmt:
	ruff format $(SOURCES)
	ruff check --fix $(SOURCES)

typecheck:
	basedpyright conversion-engine/

check: lint typecheck

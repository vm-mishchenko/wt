VENV := .venv
BIN  := $(VENV)/bin

.PHONY: setup clean test lint lint-fix

setup:
	python3 -m venv $(VENV)
	$(BIN)/pip install -e ".[dev]"
	@echo ""
	@echo "Add to ~/.zshrc"
	@echo '  export PATH="$(CURDIR)/$(BIN):$$PATH"'
	@echo "Reload shell:"
	@echo "  source ~/.zshrc"

clean:
	rm -rf $(VENV) src/*.egg-info build dist

test:
	$(BIN)/pytest tests/

lint:
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests

lint-fix:
	$(BIN)/ruff check --fix src tests
	$(BIN)/ruff format src tests

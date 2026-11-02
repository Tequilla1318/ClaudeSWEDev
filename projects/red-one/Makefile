.PHONY: run test lint fmt install

install:
	pip install -e ".[dev]"

run:
	python -m red_one

test:
	pytest -q

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff format .
	ruff check --fix .

.PHONY: install data build app test lint bench freshness all

install:
	pip install -e ".[dev]"

data:
	python -m pulse.cli data

build:
	python -m pulse.cli build

freshness:
	python -m pulse.cli freshness

app:
	streamlit run app/Home.py

test:
	pytest

lint:
	ruff check . && ruff format --check .

bench:
	python scripts/bench_store.py

all: data build test

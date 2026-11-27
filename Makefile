install:
	poetry install

test:
	poetry run pytest

mongo:
	docker compose up -d mongo

consumer:
	poetry run python -m consumer

propagator:
	poetry run python -m propagator

.PHONY: install test mongo consumer propagator

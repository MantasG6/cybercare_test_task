install:
	poetry install

test:
	poetry run pytest

mongo:
	docker compose up -d mongo

consumer:
	poetry run python -m consumer

.PHONY: install test mongo consumer

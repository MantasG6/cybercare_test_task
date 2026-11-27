install:
	poetry install

test:
	poetry run pytest

mongo:
	docker compose up -d mongo

.PHONY: install test mongo

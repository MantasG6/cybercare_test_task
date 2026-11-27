# CyberCare event services

Two Python services:

- **Propagator** (`propagator/`) sends a random event from an events file to an HTTP endpoint every N seconds.
- **Consumer** (`consumer/`) accepts events on `POST /event`, validates them and stores valid ones in MongoDB.

## Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker (for MongoDB and for the tests)

## Quickstart

```sh
make install   # install dependencies
make run       # start MongoDB, the consumer and the propagator
```

`make run` starts MongoDB in Docker, then runs both services side by side. Press Ctrl+C to stop them; `docker compose down` stops MongoDB.
The propagator may log one failed send at startup if the consumer is not listening yet. It keeps going.

Other targets:

| Target | What it does |
|---|---|
| `make mongo` | Start MongoDB in Docker (`docker compose up -d mongo`) |
| `make consumer` | Run the consumer |
| `make propagator` | Run the propagator |
| `make test` | Run the tests (Testcontainers starts its own MongoDB) |

## Configuration

Each service reads a TOML file. Pass a different one with `--config PATH`, for example `poetry run python -m propagator --config my.toml`.

`config/propagator.toml`

| Key | Meaning |
|---|---|
| `interval_seconds` | Seconds between two sent events |
| `endpoint_url` | URL the events are POSTed to |
| `events_file` | Path to the JSON array of events to choose from |

`config/consumer.toml`

| Key | Meaning |
|---|---|
| `host`, `port` | Address the HTTP API listens on |
| `mongo.uri` | MongoDB connection string |
| `mongo.database`, `mongo.collection` | Where events are stored |

## API

`POST /event` accepts **one** event per request:

```json
{"event_type": "message", "event_payload": "hello"}
```

Both fields must be strings, and no other fields are allowed. Valid events get `201` and are stored with a `received_at` timestamp; anything else gets `422`.
The task shows the template inside `[ ]`. That is read as "an event looks like this", because the propagator sends one event at a time.

To see what has been stored:

```sh
docker compose exec mongo mongosh events --eval 'db.events.find()'
```

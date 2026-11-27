import pytest
from pymongo import MongoClient
from testcontainers.community.mongodb import MongoDbContainer


@pytest.fixture(scope="session")
def mongo_client():
    with MongoDbContainer("mongo:7") as container:
        client = MongoClient(container.get_connection_url())
        yield client
        client.close()


@pytest.fixture
def collection(mongo_client):
    collection = mongo_client["test"]["events"]
    yield collection
    collection.drop()

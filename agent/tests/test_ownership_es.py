import os
import uuid

import pytest
from crm_agent.ownership import EsOwnership

pytestmark = pytest.mark.es


async def test_es_ownership():
    from elasticsearch import AsyncElasticsearch
    from langgraph_checkpoint_elasticsearch import SessionOwnershipStore

    client = AsyncElasticsearch(os.environ.get("ES_URL", "http://localhost:9200"))
    try:
        store = SessionOwnershipStore(client, index=f"owners_test_{uuid.uuid4().hex[:8]}")
        await store.setup()
        own = EsOwnership(store)
        assert await own.claim("t1", "alice") is True
        assert await own.claim("t1", "bob") is False
        assert await own.claim("t1", "alice") is True
    finally:
        await client.close()

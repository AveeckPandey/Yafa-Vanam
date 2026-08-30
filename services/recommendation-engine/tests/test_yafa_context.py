"""RAG-chat context helpers keep live commerce data out of the vector store."""
from app.yafa.context import detect_fact_type, detect_live_data_domain, fact_chunk_types, resolve_page_product
from app.yafa.schemas import PageContext


def test_detect_live_data_domains():
    assert detect_live_data_domain("Is this in stock?") == "inventory"
    assert detect_live_data_domain("what's the price") == "price"
    assert detect_live_data_domain("where is my order") == "order_status"
    assert detect_live_data_domain("what does it smell like") is None


def test_detects_and_scopes_product_facts():
    assert detect_fact_type("What does this smell like?") == "scent"
    assert detect_fact_type("What ingredients does this contain?") == "ingredients"
    assert "ingredients_concept" in fact_chunk_types("ingredients")
    assert resolve_page_product(PageContext(type="product", product_id="yv-frag-010")) == {
        "id": "yv-frag-010"
    }

"""Read-only health audit of the production vector database (no writes)."""
import os
import sys

import psycopg

dsn = os.environ["SUPA_DSN"]

with psycopg.connect(dsn, connect_timeout=10) as conn:
    cur = conn.cursor()

    print("== embedding space identity ==")
    try:
        cur.execute("SELECT * FROM rag_embedding_metadata")
        cols = [d[0] for d in cur.description]
        for row in cur.fetchall():
            print(" ", dict(zip(cols, row)))
    except psycopg.errors.UndefinedTable:
        print("  (metadata table missing)")

    print("== ingestion runs ==")
    cur.execute("SELECT * FROM rag_ingestion_runs ORDER BY 1 DESC LIMIT 3")
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        print(" ", dict(zip(cols, row)))

    print("== chunk composition ==")
    cur.execute(
        "SELECT chunk_type, trust_level, count(*) FROM rag_chunks "
        "GROUP BY 1,2 ORDER BY 3 DESC"
    )
    for chunk_type, trust, n in cur.fetchall():
        print(f"  {chunk_type:<28} {trust:<24} {n}")

    cur.execute(
        "SELECT customer_factual_eligible, count(*) FROM rag_chunks GROUP BY 1"
    )
    print("  factual eligibility:", dict(cur.fetchall()))

    cur.execute("SELECT count(*) FROM rag_chunks WHERE embedding IS NULL")
    print("  chunks missing embedding:", cur.fetchone()[0])

    print("== aliases ==")
    cur.execute("SELECT count(*) FROM rag_product_aliases")
    print("  product aliases:", cur.fetchone()[0])

    print("== pgvector operator sanity (self-query, read-only) ==")
    cur.execute(
        """
        SELECT d.product_name, c2.chunk_type,
               c1.embedding <=> c2.embedding AS distance
        FROM rag_chunks c1
        JOIN rag_chunks c2 ON c2.id <> c1.id AND c2.embedding IS NOT NULL
        JOIN rag_documents d ON d.id = c2.document_id
        WHERE c1.id = (SELECT id FROM rag_chunks WHERE embedding IS NOT NULL LIMIT 1)
        ORDER BY c1.embedding <=> c2.embedding
        LIMIT 3
        """
    )
    for chunk_type, name, dist in cur.fetchall():
        print(f"  nearest: {name} [{chunk_type}] distance={dist:.4f}")

    print("== schema migrations recorded ==")
    cur.execute("SELECT * FROM rag_schema_migrations ORDER BY 1")
    for row in cur.fetchall():
        print(" ", row)

print("PROBE OK - no writes performed")

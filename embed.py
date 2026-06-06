"""Embedding + vector store + retrieval for the CUNY financial aid RAG system.

Pipeline stage: Embedding + Vector Store -> Retrieval (see planning.md
"Architecture"). This is Milestone 4.

This script:
  1. Runs the ingestion pipeline from ingest.py to get the chunks
  2. Embeds each chunk locally with sentence-transformers all-MiniLM-L6-v2
  3. Stores the embeddings in ChromaDB in a "cuny_financial_aid" collection
  4. Tests retrieval with 3 sample queries, printing the top 4 chunks for each
  5. For each hit, prints the chunk text, source filename, and distance score

Retrieval settings come from planning.md "Retrieval Approach":
  - Embedding model: all-MiniLM-L6-v2 (via sentence-transformers), runs locally
  - Top-k: 4
  - Vector store: ChromaDB (local, no account needed)

Distance is COSINE distance (the collection is created with hnsw:space=cosine,
since ChromaDB defaults to squared-L2). Lower is more similar:
  < 0.5      -> good match
  0.6 - 0.7+ -> weak match
"""

import sys

import chromadb
from sentence_transformers import SentenceTransformer

from ingest import chunk_documents, load_documents, DOCUMENTS_DIR

# Reddit comments contain emoji and smart quotes; force UTF-8 stdout on Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# --- Retrieval settings (from planning.md "Retrieval Approach") ---------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "cuny_financial_aid"
TOP_K = 4

# Persist the vector store locally so Milestone 5 (generation) can reuse it
# without re-embedding every run.
CHROMA_PATH = "chroma_db"

# Cosine-distance interpretation thresholds (see module docstring).
GOOD_MATCH_MAX = 0.5
WEAK_MATCH_MIN = 0.6

TEST_QUERIES = [
    "how long does financial aid refund take",
    "does TAP cover summer classes",
    "what happens to financial aid if I fail a class",
]


def build_chunks():
    """Run the ingestion pipeline from ingest.py and return the chunks."""
    texts, sources = load_documents(DOCUMENTS_DIR)
    return chunk_documents(texts, sources)


def build_collection(chunks, model):
    """Embed the chunks and (re)build the ChromaDB collection.

    The collection is recreated from scratch each run so repeated runs don't
    accumulate duplicate vectors. Uses cosine distance to match the thresholds
    documented above.
    """
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Drop any existing collection so we start clean.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        # Collection didn't exist yet -- nothing to delete.
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    documents = [chunk.page_content for chunk in chunks]
    metadatas = [chunk.metadata for chunk in chunks]
    ids = [f"chunk_{i}" for i in range(len(chunks))]

    print(f"Embedding {len(documents)} chunks with {EMBEDDING_MODEL} ...")
    embeddings = model.encode(documents, show_progress_bar=False).tolist()

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    print(f"Stored {collection.count()} chunks in collection '{COLLECTION_NAME}'.")
    return collection


def quality_label(distance):
    """Human-readable verdict for a cosine distance score."""
    if distance < GOOD_MATCH_MAX:
        return "good"
    if distance < WEAK_MATCH_MIN:
        return "ok"
    return "weak"


def load_model():
    """Load the sentence-transformers embedding model (used by ingest + app)."""
    return SentenceTransformer(EMBEDDING_MODEL)


def get_collection():
    """Open the EXISTING persistent ChromaDB collection (no re-embedding).

    Use this from downstream stages (e.g. app.py) after embed.py has already
    built the collection. Raises if the collection hasn't been created yet.
    """
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_collection(COLLECTION_NAME)


def retrieve(collection, model, query, k=TOP_K):
    """Embed `query` and return the top-k chunks as a list of dicts.

    Each dict has: text, source, distance. This is the single retrieval
    function shared by embed.py's self-test and app.py's RAG pipeline.
    """
    query_embedding = model.encode([query]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=k)

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    return [
        {"text": doc, "source": meta.get("source", "?"), "distance": dist}
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]


def run_query(collection, model, query):
    """Embed a query, retrieve top-k chunks, and print them with scores."""
    hits = retrieve(collection, model, query)

    print("\n" + "=" * 70)
    print(f"QUERY: {query}")
    print("=" * 70)

    for rank, hit in enumerate(hits, start=1):
        label = quality_label(hit["distance"])
        print(
            f"\n[{rank}] source={hit['source']}  "
            f"distance={hit['distance']:.4f}  ({label})"
        )
        print("-" * 70)
        print(hit["text"])
        print("-" * 70)


def main():
    chunks = build_chunks()
    print(f"Got {len(chunks)} chunks from the ingestion pipeline.")

    model = SentenceTransformer(EMBEDDING_MODEL)
    collection = build_collection(chunks, model)

    print(f"\nRunning {len(TEST_QUERIES)} test queries (top-{TOP_K} each) ...")
    for query in TEST_QUERIES:
        run_query(collection, model, query)


if __name__ == "__main__":
    main()

"""Document ingestion + chunking for the CUNY financial aid RAG system.

Pipeline stage: Document Ingestion -> Chunking (see planning.md "Architecture").

This script:
  1. Loads every .txt file from the documents/ folder
  2. Cleans the text (trims whitespace, collapses repeated blank lines)
  3. Splits each document into chunks with RecursiveCharacterTextSplitter,
     measured in TOKENS (400-token chunks, 50-token overlap)
  4. Prints the total chunk count
  5. Prints 5 random chunks for a readability spot-check

Each chunk carries metadata with the source filename it came from, so later
stages (embedding / retrieval) can surface source citations.

Chunk size and overlap come straight from planning.md's Chunking Strategy.
RecursiveCharacterTextSplitter measures length in CHARACTERS by default, so we
build it via `from_tiktoken_encoder` to count TOKENS instead, matching the spec.
tiktoken runs locally with no API key.
"""

import glob
import os
import random
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Reddit comments contain emoji and smart quotes. The default Windows console
# encoding (cp1252) can't print those, so force stdout to UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# --- Chunking parameters (from planning.md "Chunking Strategy") ---------------
CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 50

DOCUMENTS_DIR = "documents"

# How many random chunks to print for the readability spot-check.
NUM_SAMPLE_CHUNKS = 5


def clean_text(text):
    """Normalize whitespace without destroying the document's structure.

    We deliberately keep single blank lines between blocks: the thread files
    separate each comment with a blank line, and RecursiveCharacterTextSplitter
    splits on "\\n\\n" first. Preserving those boundaries is what lets recursive
    chunking respect comment boundaries (the reasoning given in planning.md).
    """
    # Normalize line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip trailing/leading spaces on each line and drop lines that are only
    # whitespace down to a true empty line.
    lines = [line.strip() for line in text.split("\n")]

    # Collapse runs of 2+ blank lines into a single blank line.
    cleaned_lines = []
    previous_blank = False
    for line in lines:
        is_blank = line == ""
        if is_blank and previous_blank:
            continue
        cleaned_lines.append(line)
        previous_blank = is_blank

    return "\n".join(cleaned_lines).strip()


def load_documents(documents_dir):
    """Load and clean every .txt file in `documents_dir`.

    Returns two parallel lists: cleaned text bodies and their source filenames.
    """
    paths = sorted(glob.glob(os.path.join(documents_dir, "*.txt")))
    if not paths:
        raise FileNotFoundError(
            f"No .txt files found in '{documents_dir}/'. "
            "Run from the project root where the documents/ folder lives."
        )

    texts = []
    sources = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        cleaned = clean_text(raw)
        if not cleaned:
            print(f"  Skipping {os.path.basename(path)} (empty after cleaning)")
            continue

        texts.append(cleaned)
        sources.append(os.path.basename(path))

    return texts, sources


def build_splitter():
    """RecursiveCharacterTextSplitter that measures length in tokens."""
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
    )


def chunk_documents(texts, sources):
    """Split documents into chunks, attaching the source filename to each.

    Returns a list of langchain Document objects. Each has `.page_content`
    (the chunk text) and `.metadata["source"]` (the originating filename).
    """
    splitter = build_splitter()
    metadatas = [{"source": source} for source in sources]
    return splitter.create_documents(texts, metadatas=metadatas)


def print_sample_chunks(chunks, k):
    """Print up to `k` randomly chosen chunks for a manual readability check."""
    sample_size = min(k, len(chunks))
    sample = random.sample(chunks, sample_size)

    print(f"\n--- {sample_size} random chunks for verification ---")
    for i, chunk in enumerate(sample, start=1):
        source = chunk.metadata.get("source", "?")
        print(f"\n[Sample {i}/{sample_size}]  source={source}")
        print("-" * 60)
        print(chunk.page_content)
        print("-" * 60)


def main():
    print(f"Loading .txt files from '{DOCUMENTS_DIR}/' ...")
    texts, sources = load_documents(DOCUMENTS_DIR)
    print(f"Loaded {len(texts)} document(s).")

    chunks = chunk_documents(texts, sources)
    print(
        f"\nTotal chunks produced: {len(chunks)} "
        f"(size={CHUNK_SIZE_TOKENS} tokens, overlap={CHUNK_OVERLAP_TOKENS} tokens)"
    )

    print_sample_chunks(chunks, NUM_SAMPLE_CHUNKS)


if __name__ == "__main__":
    main()

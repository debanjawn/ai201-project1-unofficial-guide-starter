"""Grounded generation + web interface for the CUNY financial aid RAG system.

Pipeline stage: Retrieval -> Generation (see planning.md "Architecture").
This is Milestone 5.

Flow per question:
  1. Retrieve the top-4 most relevant chunks from the ChromaDB collection
     (reusing the collection, embedding model, and retrieve() from embed.py)
  2. Build a context block from those chunks, each tagged with its source
  3. Ask Groq's llama-3.3-70b-versatile to answer ONLY from that context
  4. Surface source attribution (which Reddit threads the answer came from)
  5. Serve all of this through a Gradio web interface

Grounding is enforced two ways:
  - The system prompt forbids outside knowledge and mandates the exact
    fallback phrase when the context is insufficient.
  - The context is the ONLY place the model sees thread content, and each
    block is labeled with its source so answers can be attributed.

The Groq API key is loaded from .env via python-dotenv.
"""

import os
import sys

import gradio as gr
from dotenv import load_dotenv
from groq import Groq

from embed import DOCUMENTS_DIR, TOP_K, get_collection, load_model, retrieve

# Reddit comments contain emoji and smart quotes; force UTF-8 stdout on Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# --- Generation settings (from planning.md "Architecture") --------------------
GROQ_MODEL = "llama-3.3-70b-versatile"

# Exact phrase the model must use when the context can't answer the question.
INSUFFICIENT_INFO = "I don't have enough information on that."

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions about CUNY financial "
    "aid (TAP, Pell, disbursements, refunds) for students. You answer using "
    "ONLY the context provided to you, which comes from real r/CUNY Reddit "
    "threads.\n\n"
    "Rules:\n"
    "1. Use ONLY information found in the provided context. Do NOT use any "
    "outside or general knowledge.\n"
    f'2. If the context does not contain enough information to answer, reply '
    f'EXACTLY with: "{INSUFFICIENT_INFO}" and nothing else.\n'
    "3. Do not make up facts, numbers, dates, or policies that are not in the "
    "context.\n"
    "4. Keep answers concise and practical. Remember this is unofficial "
    "student advice, not official CUNY policy.\n"
)

# Load the Groq API key from .env.
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY or GROQ_API_KEY == "your_key_here":
    raise RuntimeError(
        "GROQ_API_KEY is missing or still the placeholder. Copy .env.example "
        "to .env and set your real key from https://console.groq.com"
    )

# Load shared resources once at startup (model, vector store, LLM client).
print("Loading embedding model and ChromaDB collection ...")
MODEL = load_model()
COLLECTION = get_collection()
GROQ_CLIENT = Groq(api_key=GROQ_API_KEY)


def load_source_titles(documents_dir):
    """Map each source filename to its thread title + URL for nice citations.

    Reads the first two lines of every .txt file, which by convention are
    "THREAD: <title>" and "URL: <url>" (see how the documents were saved).
    """
    titles = {}
    if not os.path.isdir(documents_dir):
        return titles

    for filename in os.listdir(documents_dir):
        if not filename.endswith(".txt"):
            continue
        path = os.path.join(documents_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            first = f.readline().strip()
            second = f.readline().strip()
        title = first[len("THREAD:"):].strip() if first.startswith("THREAD:") else filename
        url = second[len("URL:"):].strip() if second.startswith("URL:") else ""
        titles[filename] = {"title": title, "url": url}
    return titles


SOURCE_TITLES = load_source_titles(DOCUMENTS_DIR)


def build_context(hits):
    """Turn retrieved chunks into a labeled context block for the prompt."""
    blocks = []
    for i, hit in enumerate(hits, start=1):
        blocks.append(
            f"[Source {i} - {hit['source']}]\n{hit['text']}"
        )
    return "\n\n".join(blocks)


def format_sources(hits):
    """Build a readable source-attribution string from retrieved chunks.

    Lists each unique source thread once (with its title, URL, and the best /
    closest distance among its retrieved chunks).
    """
    best_by_source = {}
    for hit in hits:
        source = hit["source"]
        if source not in best_by_source or hit["distance"] < best_by_source[source]:
            best_by_source[source] = hit["distance"]

    lines = []
    # Order sources by best (lowest) distance so the most relevant is first.
    for source, distance in sorted(best_by_source.items(), key=lambda kv: kv[1]):
        info = SOURCE_TITLES.get(source, {})
        title = info.get("title", source)
        url = info.get("url", "")
        line = f"- {title} ({source}, distance={distance:.3f})"
        if url:
            line += f"\n  {url}"
        lines.append(line)
    return "\n".join(lines)


def answer_question(question):
    """Full RAG step: retrieve -> generate -> return (answer, sources)."""
    question = (question or "").strip()
    if not question:
        return "Please enter a question.", ""

    hits = retrieve(COLLECTION, MODEL, question, k=TOP_K)
    context = build_context(hits)

    user_prompt = (
        f"Context from r/CUNY threads:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above."
    )

    completion = GROQ_CLIENT.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    answer = completion.choices[0].message.content.strip()

    # If the model couldn't answer from context, don't show misleading sources.
    if INSUFFICIENT_INFO.lower() in answer.lower():
        return answer, "No sources — the documents don't cover this question."

    return answer, format_sources(hits)


def build_interface():
    """Build the Gradio web interface."""
    with gr.Blocks(title="CUNY Financial Aid — The Unofficial Guide") as demo:
        gr.Markdown(
            "# CUNY Financial Aid — The Unofficial Guide\n"
            "Ask about TAP, Pell, disbursements, and refunds. Answers come "
            "**only** from real r/CUNY threads, with sources cited."
        )
        question = gr.Textbox(
            label="Your question",
            placeholder="e.g. How long does a financial aid refund take?",
            lines=2,
        )
        ask_button = gr.Button("Ask", variant="primary")
        answer = gr.Textbox(label="Answer", lines=8)
        sources = gr.Textbox(label="Sources", lines=6)

        ask_button.click(
            fn=answer_question, inputs=question, outputs=[answer, sources]
        )
        question.submit(
            fn=answer_question, inputs=question, outputs=[answer, sources]
        )
    return demo


def main():
    demo = build_interface()
    demo.launch()


if __name__ == "__main__":
    main()

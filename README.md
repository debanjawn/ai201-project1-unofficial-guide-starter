# The Unofficial Guide — Project 1

---

## Domain

CUNY financial aid from the student perspective — specifically the unofficial knowledge 
students share on Reddit about TAP, Pell, disbursements, and refunds. This information 
is hard to find officially because it reflects real student experiences, edge cases, and 
timeline realities that official CUNY docs don't address. For example, official sources 
won't tell you that adding summer TAP can drain your fall/spring aid, or that Chime 
releases deposits faster than Chase — but students on r/CUNY will.

---

## Document Sources

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/18t5glp/does_a_wu_mess_up_my_financial_aid/ |
| 2 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/1qazy8g/financial_aid_refunds/ |
| 3 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/1mvuvho/paying_for_college_except_were_really_broke/ |
| 4 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/1fcypzx/is_it_possible_to_get_100_financial_aid_and_is/ |
| 5 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/1hh5lgd/is_my_financial_aid_going_to_go_down/ |
| 6 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/1tby95i/understanding_financial_aid/ |
| 7 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/117wgdi/financial_aid_disbursement_megathread_faq/ |
| 8 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/1jcyrhz/how_much_am_i_supposed_to_pay/ |
| 9 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/x94w0o/a_guide_to_financial_aid_refunds_pell_tap_and/ |
| 10 | r/CUNY | Reddit thread | https://www.reddit.com/r/CUNY/comments/1frqjkg/can_pell_or_tap_pay_for_summer_classes/ |

---

## Chunking Strategy

**Chunk size:** 400 tokens

**Overlap:** 50 tokens

**Why these choices fit your documents:** Reddit threads are naturally structured by 
comments, where each comment represents one person's complete thought. Recursive 
chunking (RecursiveCharacterTextSplitter) was chosen because it splits on paragraph 
and newline boundaries first, which naturally respects comment boundaries. Fixed 
chunking was ruled out because financial aid answers vary greatly in length. Semantic 
chunking was ruled out because Reddit comments are already separated by meaning — the 
structure does that work for us. 400 tokens gives enough room to capture a full comment 
with context. 50 token overlap acts as a safety net for thoughts that span comment 
boundaries.

**Final chunk count:** 57 chunks across 10 documents

---

## Embedding Model

**Model used:** all-MiniLM-L6-v2 via sentence-transformers

**Production tradeoff reflection:** all-MiniLM-L6-v2 was chosen because it runs 
locally with no API key and no rate limits, making it ideal for this project. For a 
real production deployment, I would consider OpenAI's text-embedding-ada-002 for 
higher accuracy, but it costs money per API call and requires an internet connection. 
A multilingual model would also be worth considering since some CUNY students write 
in Spanish or other languages. Context length is less of a concern here since Reddit 
comments are short. Latency is also not an issue for this use case since queries are 
infrequent.

---

## Grounded Generation

**System prompt grounding instruction:** The system prompt instructs the model to 
answer only from the retrieved context: "Answer the question using only the information 
in the provided documents. If the documents don't contain enough information to answer, 
say 'I don't have enough information on that.' Do not use your general training 
knowledge." This is enforced structurally by only passing the 4 retrieved chunks as 
context — the model has no access to anything outside those chunks.

**How source attribution is surfaced in the response:** Source attribution is 
programmatically appended after generation — the app extracts the THREAD title and URL 
from each retrieved chunk's header lines and displays them in a separate "Retrieved 
from" box in the Gradio interface, independent of what the LLM writes.

---

## Evaluation Report

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | If I withdrew from a class but stayed above 12 credits, will it affect my financial aid? | No negative impact as long as you remain full time (12+ credits) | Correct — stated financials don't change above 12 credits, recommended contacting FA | Relevant | Accurate |
| 2 | If I was full time fall and spring, can financial aid cover full time summer classes? | TAP generally doesn't cover summer well; Pell may cover summer | Correct — explained Pell can cover summer but warned against adding summer TAP as it lowers fall/spring aid | Relevant | Accurate |
| 3 | What happens to my financial aid if I fail classes and my GPA drops to 1.7? | Bad academic standing can put aid on probation; SAP requirements must be met | Correct — mentioned SAP, Waiver of Good Academic Standing, freshman vs sophomore difference | Relevant | Accurate |
| 4 | Is it possible to get full tuition covered and still get a refund check? | Yes, if Pell + TAP exceed tuition the remainder is refunded | Correct — cited student example where aid exceeded tuition balance | Relevant | Partially accurate |
| 5 | If you get a financial aid refund, what should you do with it? | Students recommend using it for books, housing, or saving it | Generic answer about books/transport/rent — sounded like official advice rather than specific student experiences | Partially relevant | Partially accurate |

---

## Failure Case Analysis

**Question that failed:** Question 5 — "If you get a financial aid refund, what should 
you do with it?"

**What the system returned:** A generic answer recommending books, meals, transport, 
and rent — accurate but vague, and sounding like official financial aid office advice 
rather than specific student experiences from Reddit.

**Root cause (tied to a specific pipeline stage):** This is a grounding failure at the 
generation stage. The retrieved chunks for this question were loosely related 
(thread6.txt and thread9.txt) but didn't contain specific student advice about what to 
do with a refund. With weak context, the LLM fell back on its general training 
knowledge to fill in the gap, producing a plausible but non-grounded answer. The fact 
that the answer sounded exactly like what a financial aid counselor would say — not 
what a student on Reddit would say — confirms it came from training data, not the 
documents.

**What you would change to fix it:** Add more documents specifically about refund 
spending advice from students. Alternatively, tighten the grounding prompt further to 
force the model to say "I don't have enough information" when the retrieved chunks 
don't directly answer the question, rather than filling in from general knowledge.

---

## Spec Reflection

**One way the spec helped you during implementation:** Writing the chunking strategy 
in planning.md before coding forced a clear decision between fixed, recursive, and 
semantic chunking. When it came time to implement ingest.py, the reasoning was already 
documented — recursive was chosen because Reddit comments are already semantically 
separated, so the spec decision translated directly into the implementation choice 
without any ambiguity.

**One way your implementation diverged from the spec, and why:** The spec assumed 
documents would be collected via automated scraping (PRAW or the Reddit JSON API). In 
practice, Reddit returned 403 errors for all automated requests due to their API 
restrictions tightened in 2023/2024. Documents were instead manually collected by 
copying raw JSON from Reddit's .json endpoints and using Claude to parse and clean 
them into .txt files. The scrape.py file was kept with a comment documenting why 
automated scraping failed.

---

## AI Usage

**Instance 1**

- *What I gave the AI:* My Chunking Strategy and Documents sections from planning.md, 
  plus a request to implement ingest.py with RecursiveCharacterTextSplitter at 400 
  tokens chunk size and 50 token overlap
- *What it produced:* A working ingest.py that loaded all 10 documents, cleaned them, 
  and produced 57 chunks with source metadata. It also added langchain-text-splitters 
  and tiktoken to requirements.txt and fixed a Windows UTF-8 encoding issue
- *What I changed or overrode:* The chunk size and overlap were kept exactly as 
  specified in planning.md — I did not let the AI choose different values

**Instance 2**

- *What I gave the AI:* My full pipeline architecture, the embed.py retrieval approach, 
  and a request to build app.py with strict grounding, source attribution, and a 
  Gradio interface
- *What it produced:* A working app.py with the Groq LLM integration, grounding system 
  prompt, programmatic source attribution, and Gradio UI running on localhost:7860
- *What I changed or overrode:* Verified the grounding was working by testing an 
  out-of-scope question ("best pizza topping in New York") — confirmed it returned 
  "I don't have enough information on that" rather than answering from general knowledge
# NOTE: Automated scraping was attempted but failed for the following reasons:
# - Reddit returns 403 Forbidden errors when requests come from scripts
# - Reddit has aggressively blocked automated scrapers since 2023/2024
# - Changing the User-Agent to mimic a browser did not resolve the issue
# - The Reddit JSON API requires authentication for programmatic access
#
# Solution: Documents were manually collected by opening each Reddit thread,
# copying the raw JSON from the .json endpoint, and using Claude to parse
# and format the JSON into clean .txt files saved in the documents/ folder.

"""Scrape Reddit threads via the public JSON API and save each as a clean .txt file.

Uses only the `requests` library (no PRAW). Each thread URL has `.json` appended,
the response is parsed, and the title, body, and ALL comments (including nested
replies, extracted recursively) are written to documents/threadN.txt.
"""

import os
import time

import requests

# Reddit returns 403 for non-browser User-Agents, so mimic a real browser.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Seconds to wait between requests to avoid rate limiting.
REQUEST_DELAY = 2

OUTPUT_DIR = "documents"

URLS = [
    "https://www.reddit.com/r/CUNY/comments/18t5glp/does_a_wu_mess_up_my_financial_aid/",
    "https://www.reddit.com/r/CUNY/comments/1qazy8g/financial_aid_refunds/",
    "https://www.reddit.com/r/CUNY/comments/1mvuvho/paying_for_college_except_were_really_broke/",
    "https://www.reddit.com/r/CUNY/comments/1fcypzx/is_it_possible_to_get_100_financial_aid_and_is/",
    "https://www.reddit.com/r/CUNY/comments/1hh5lgd/is_my_financial_aid_going_to_go_down/",
    "https://www.reddit.com/r/CUNY/comments/1tby95i/understanding_financial_aid/",
    "https://www.reddit.com/r/CUNY/comments/117wgdi/financial_aid_disbursement_megathread_faq/",
    "https://www.reddit.com/r/CUNY/comments/1jcyrhz/how_much_am_i_supposed_to_pay/",
    "https://www.reddit.com/r/CUNY/comments/x94w0o/a_guide_to_financial_aid_refunds_pell_tap_and/",
    "https://www.reddit.com/r/CUNY/comments/1frqjkg/can_pell_or_tap_pay_for_summer_classes/",
]


def extract_comments(children, depth=0):
    """Recursively extract comments and all nested replies.

    Reddit nests each comment's replies inside its "replies" field, which is
    itself a listing with the same structure. We walk it recursively so that
    replies-to-replies (and deeper) are all captured. `depth` is used purely
    for indentation in the output to show the reply hierarchy.

    Returns a list of formatted comment strings.
    """
    lines = []
    for child in children:
        # Skip "more" stubs (collapsed comment loaders) and anything that
        # isn't an actual comment.
        if child.get("kind") != "t1":
            continue

        data = child.get("data", {})
        author = data.get("author", "[deleted]")
        body = (data.get("body") or "").strip()

        indent = "    " * depth
        lines.append(f"{indent}COMMENT by {author}:")
        for body_line in body.splitlines():
            lines.append(f"{indent}{body_line}")
        lines.append("")

        # Recurse into nested replies. `replies` is "" when there are none.
        replies = data.get("replies")
        if isinstance(replies, dict):
            reply_children = replies.get("data", {}).get("children", [])
            lines.extend(extract_comments(reply_children, depth + 1))

    return lines


def scrape_thread(url):
    """Fetch a single thread's JSON and return its formatted text content."""
    json_url = url.rstrip("/") + "/.json"
    response = requests.get(json_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    # data[0] is the post listing, data[1] is the comment listing.
    post = data[0]["data"]["children"][0]["data"]
    title = post.get("title", "").strip()
    selftext = (post.get("selftext") or "").strip()

    lines = [
        f"THREAD: {title}",
        f"URL: {url}",
        "",
        "POST:",
        selftext if selftext else "[no body text]",
        "",
        "=" * 60,
        "",
    ]

    comment_children = data[1]["data"]["children"]
    comment_lines = extract_comments(comment_children)
    if comment_lines:
        lines.extend(comment_lines)
    else:
        lines.append("[no comments]")

    return "\n".join(lines)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for index, url in enumerate(URLS, start=1):
        print(f"Scraping thread {index}: {url}")
        try:
            content = scrape_thread(url)
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"  Failed to scrape {url}: {exc}")
            continue

        out_path = os.path.join(OUTPUT_DIR, f"thread{index}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Saved {out_path}")

        # Delay between requests to be polite and avoid rate limiting.
        if index < len(URLS):
            time.sleep(REQUEST_DELAY)

    print("Done.")


if __name__ == "__main__":
    main()

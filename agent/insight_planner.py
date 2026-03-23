import re
from agent.llm import ask_llm


def plan_insights(schema_context):

    prompt = f"""-- Analytics mart names for this schema:
{schema_context}
-- List of 6 useful snake_case mart names, one per line:
-- total_revenue_by_customer
-- monthly_order_trends
--"""

    response = ask_llm(prompt)

    insights = []

    for line in response.split("\n"):

        line = line.strip()

        # strip comment markers the model might echo back
        line = re.sub(r"^--\s*", "", line)

        # strip numbering like "1." "1)" "- "
        line = re.sub(r"^[\d\.\-\*\)]+\s*", "", line)

        # normalize to snake_case
        line = line.lower().strip()
        line = re.sub(r"\s+", "_", line)

        # keep only valid characters
        line = re.sub(r"[^a-z0-9_]", "", line)

        # skip empty
        if not line:
            continue

        # skip lines that are clearly prose (contain common filler words)
        skip_words = {"here", "sure", "following", "these", "some", "based",
                      "the", "for", "are", "is", "and", "with", "note", "please",
                      "you", "can", "will", "this", "that", "also", "below"}
        first_word = line.split("_")[0]
        if first_word in skip_words:
            continue

        # skip very long names (LLM wrote a sentence)
        if len(line) > 60:
            continue

        insights.append(line)

    # deduplicate while preserving order
    seen = set()
    unique = []
    for i in insights:
        if i not in seen:
            seen.add(i)
            unique.append(i)

    return unique
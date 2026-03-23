import json
import re


def extract_json(text):

    text = text.replace("```json", "")
    text = text.replace("```", "")

    match = re.search(r"\{[\s\S]*\}", text)

    if not match:
        raise ValueError("No JSON found in LLM response")

    json_text = match.group(0)

    try:
        return json.loads(json_text)

    except Exception:

        # attempt to repair JSON
        json_text = json_text.replace("'", '"')

        json_text = re.sub(r'(\w+):', r'"\1":', json_text)

        try:
            return json.loads(json_text)
        except Exception as e:

            print("\nRAW LLM RESPONSE:")
            print(text)

            raise ValueError(f"JSON parsing failed: {e}")
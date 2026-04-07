import json


def parse_json_response(raw_text, fallback):
    text = (raw_text or "").strip()
    if not text:
        return fallback

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting json payload from markdown code block.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return fallback

    return fallback


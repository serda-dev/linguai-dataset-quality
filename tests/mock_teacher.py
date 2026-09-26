"""Deterministic OpenAI-compatible fake; no external requests."""
from fastapi import FastAPI

app = FastAPI()


@app.post("/v1/chat/completions")
def completion(body: dict):
    import json

    user = body["messages"][1]["content"]
    doc_id = user.split("DOCUMENT_ID:\n", 1)[1].split("\n", 1)[0]
    if "MOCK_INVALID_JSON" in user:
        content = "{invalid"
    else:
        if "MOCK_WRONG_ID" in user:
            doc_id = "incorrect"
        content = json.dumps({"id": doc_id, "type": "reference", "q": {
            "language": 4, "coherence": 4, "information": 4, "cleanliness": 1,
            "structure": 4, "utility": 3}, "noise": ["boilerplate_ui"]})
    return {"choices": [{"message": {"content": content}}]}

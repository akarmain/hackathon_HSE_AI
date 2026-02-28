from app.features.genai.client import GenAPIClient


def test_extract_text_from_choices_message_content() -> None:
    client = GenAPIClient(api_key="test", base_url="https://example.test")
    payload = {
        "status": "success",
        "result": [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "<!doctype html><html><body><h1>Slide</h1></body></html>",
                        }
                    }
                ]
            }
        ],
    }

    text = client.extract_text(payload)
    assert text.lower().startswith("<!doctype html>")
    assert "<h1>Slide</h1>" in text


def test_extract_text_from_content_blocks() -> None:
    client = GenAPIClient(api_key="test", base_url="https://example.test")
    payload = {
        "result": [
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "plain text answer"},
                            ]
                        }
                    }
                ]
            }
        ]
    }

    text = client.extract_text(payload)
    assert text == "plain text answer"


def test_extract_text_falls_back_to_stringified_payload() -> None:
    client = GenAPIClient(api_key="test", base_url="https://example.test")
    payload = {"status": "success", "result": [{"id": "x"}]}

    text = client.extract_text(payload)
    assert text.startswith("{")
    assert "'status': 'success'" in text

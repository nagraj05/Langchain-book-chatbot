from app.rag import _parse_suggestions


def test_json_suggestions_are_parsed() -> None:
    content = '["What is the central argument?", "How is retrieval evaluated?", "Which limitations remain?"]'

    assert _parse_suggestions(content) == [
        "What is the central argument?",
        "How is retrieval evaluated?",
        "Which limitations remain?",
    ]


def test_numbered_suggestions_are_parsed() -> None:
    content = "1. What problem does the author solve?\n2. Which tools are compared?\n3. What tradeoffs are identified?"

    assert _parse_suggestions(content) == [
        "What problem does the author solve?",
        "Which tools are compared?",
        "What tradeoffs are identified?",
    ]

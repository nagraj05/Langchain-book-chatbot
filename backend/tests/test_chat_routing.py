from app.rag import _casual_response


def test_greetings_bypass_retrieval() -> None:
    response = _casual_response("Hi!")

    assert response is not None
    assert "BOOKBot" in response


def test_thanks_bypass_retrieval() -> None:
    assert _casual_response("Thank you so much") is not None


def test_book_questions_continue_to_retrieval() -> None:
    assert _casual_response("What does the author recommend for deployment?") is None

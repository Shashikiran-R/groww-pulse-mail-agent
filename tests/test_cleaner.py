import pytest
from src.pipeline.cleaner import TextCleaner

@pytest.fixture
def cleaner():
    return TextCleaner()

def test_html_decoding(cleaner):
    review = {"text": "can&#39;t login!!!! 😡😡"}
    res = cleaner.clean(review)
    assert res["cleaned_text"] == "can't login!"
    assert res["emojis"] == ["😡", "😡"]

def test_whitespace_normalisation(cleaner):
    review = {"text": "  bad  app\t\n "}
    res = cleaner.clean(review)
    assert res["cleaned_text"] == "bad app"

def test_url_removal(cleaner):
    review = {"text": "check https://groww.in ok"}
    res = cleaner.clean(review)
    assert res["cleaned_text"] == "check ok"

def test_email_removal(cleaner):
    review = {"text": "contact me at test@example.com"}
    res = cleaner.clean(review)
    assert res["cleaned_text"] == "contact me at"

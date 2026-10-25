import pytest
from src.pipeline.normaliser import TextNormaliser

@pytest.fixture
def normaliser():
    abbreviations = {
        "txn": "transaction",
        "amt": "amount",
        "govt": "government"
    }
    return TextNormaliser(abbreviations)

def test_abbreviation_expansion(normaliser):
    # Has more than 8 words to pass the filter
    review = {"cleaned_text": "txn failed on amt 2,00,000 and it is very annoying indeed", "text": "Txn failed on amt 2,00,000 and it is very annoying indeed"}
    res = normaliser.normalise(review)
    assert res is not None
    assert res["normalised_text"] == "transaction failed on amount 2,00,000 and it is very annoying indeed"
    assert res["original_text"] == "Txn failed on amt 2,00,000 and it is very annoying indeed"

def test_hinglish_detection(normaliser):
    review = {"cleaned_text": "bahut bekar app hai but I still need to use it everyday"}
    res = normaliser.normalise(review)
    assert res is not None
    assert res["is_hinglish"] is True

def test_unicode_nfkc(normaliser):
    review = {"cleaned_text": "ﬁnance app² is completely useless and I hate it so much"}
    res = normaliser.normalise(review)
    assert res is not None
    assert res["normalised_text"] == "finance app2 is completely useless and i hate it so much"

def test_word_count_filter(normaliser):
    review = {"cleaned_text": "short review"}
    res = normaliser.normalise(review)
    assert res is not None # Does NOT drop short reviews

def test_date_and_rating_normalisation(normaliser):
    review = {
        "cleaned_text": "this is a very long review with enough words to pass the check",
        "date": "2026-09-15T00:00:00Z",
        "rating": "2"
    }
    res = normaliser.normalise(review)
    assert res is not None
    assert res["date"] == "2026-09-15T00:00:00+00:00"
    assert res["rating"] == 2

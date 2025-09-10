# tests/test_nl_comparatives.py
from nl_comparatives import parse_comparative

def test_at_least_ge():
    assert parse_comparative("when score is at least 90") == ("score", ">=", 90)

def test_at_most_le():
    assert parse_comparative("tries are at most 3") == ("tries", "<=", 3)

def test_greater_than_gt():
    assert parse_comparative("age > 18") == ("age", ">", 18)

def test_fewer_than_lt():
    assert parse_comparative("count fewer than 5") == ("count", "<", 5)

def test_equals_200():
    assert parse_comparative("status equals 200") == ("status", "==", 200)

def test_is_not_ne():
    assert parse_comparative("unless status is not 200:") == ("status", "!=", 200)

def test_string_rhs():
    assert parse_comparative("env equal to 'prod'") == ("env", "==", "prod")

def test_courtesy_and_punct():
    assert parse_comparative("score is at least 90, thanks!") == ("score", ">=", 90)

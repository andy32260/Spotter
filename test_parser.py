import os

import parser
from parser import parse

# Tests must never call the network: make sure no key is set.
os.environ.pop("GROQ_API_KEY", None)


def check(text, intent, weight=None, reps=None, days=None, effort=None):
    expected = {"intent": intent, "weight": weight, "reps": reps, "days": days,
                "effort": effort, "source": "regex"}
    result = parse(text)
    assert result == expected, f"{text!r}: expected {expected}, got {result}"


def parse_with_fake_llm(text, fake_llm):
    """Run parse() as if a key and model were set, with the AI replaced by fake_llm."""
    real_llm = parser.parse_llm
    os.environ["GROQ_API_KEY"] = "test-key"
    os.environ["GROQ_MODEL"] = "test-model"
    parser.parse_llm = fake_llm
    try:
        return parse(text)
    finally:
        parser.parse_llm = real_llm
        del os.environ["GROQ_API_KEY"], os.environ["GROQ_MODEL"]


def test_weight_with_unit_and_bare_reps():
    check("only got 8 at 60 kilos", "set_done", 60.0, 8)


def test_two_bare_numbers_are_weight_then_reps():
    check("60 for 8", "set_done", 60.0, 8)


def test_number_words_become_reps():
    check("got eight", "set_done", None, 8)


def test_equipment_taken():
    check("the bench is taken", "equipment_taken")


def test_pain():
    check("my shoulder hurt", "pain")


def test_more_pain_words():
    for text in ["my elbow is killing me", "think I tweaked my back"]:
        result = parser.parse_regex(text)
        assert result["intent"] == "pain", f"{text!r} gave {result}"


def test_pain_wins_over_set_done():
    check("it hurt on rep 8", "pain")


def test_undo():
    check("scratch that", "undo")


def test_undo_keeps_corrected_numbers():
    result = parser.parse_regex("scratch that it was 60 kilos for 8 reps")
    assert result == {"intent": "undo", "weight": 60.0, "reps": 8, "days": None, "effort": None}


def test_overview():
    assert parser.parse_regex("what exercises should I do")["intent"] == "overview"


def test_days_per_week():
    check("4 days", "overview", days=4)        # answers "how many days a week?"
    check("three days a week", "overview", days=3)


def test_whats_first_is_next():
    check("what's first", "next")


def test_form():
    assert parser.parse_regex("how do I do this")["intent"] == "form"
    assert parser.parse_regex("how do I do this, it hurts")["intent"] == "pain"


def test_summary():
    assert parser.parse_regex("how did I do")["intent"] == "summary"
    assert parser.parse_regex("give me a recap")["intent"] == "summary"


def test_effort():
    check("felt like nothing", "effort", effort="easy")
    check("yeah that was alright", "effort", effort="right")
    check("that was a struggle", "effort", effort="hard")
    check("ok but heavy", "effort", effort="hard")   # mixed: the safer answer wins
    check("I took a look", "unknown")                # "ok" only as a whole word


def test_skip():
    check("skip warm-up", "skip")
    check("skip", "skip")


def test_pain_wins_over_effort():
    check("that was easy but my wrist hurts", "pain")


def test_pain_wins_over_undo():
    check("that was wrong it hurt", "pain")


def test_next():
    check("what's next", "next")


def test_unknown():
    check("banana", "unknown")


def test_pain_wins_even_with_a_key():
    def ai_must_not_be_called(text):
        raise AssertionError("The AI was called for a pain sentence")

    result = parse_with_fake_llm("my knee hurts, got 8", ai_must_not_be_called)
    assert result == {"intent": "pain", "weight": None, "reps": None, "days": None, "effort": None,
                      "source": "regex"}


def test_ai_answer_is_used():
    def fake(text):
        return {"intent": "set_done", "weight": 60, "reps": 8, "days": None, "effort": None}

    result = parse_with_fake_llm("did 60 for eight", fake)
    assert result == {"intent": "set_done", "weight": 60.0, "reps": 8, "days": None, "effort": None,
                      "source": "ai"}


def test_numbers_the_user_never_said_are_dropped():
    def fake(text):    # the AI invents "6 days" for a question with no number
        return {"intent": "overview", "weight": None, "reps": None, "days": 6,
                "effort": None}

    result = parse_with_fake_llm("what workout should I do", fake)
    assert result == {"intent": "overview", "weight": None, "reps": None,
                      "days": None, "effort": None, "source": "ai"}


def test_invalid_ai_answer_falls_back_to_regex():
    def fake(text):
        return {"intent": "dance", "weight": "heavy", "reps": None, "days": None, "effort": None}

    result = parse_with_fake_llm("60 for 8", fake)
    assert result == {"intent": "set_done", "weight": 60.0, "reps": 8, "days": None, "effort": None,
                      "source": "regex"}


if __name__ == "__main__":
    tests = [f for name, f in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"All {len(tests)} parser tests passed.")

"""Sanity tests for coach.py. Run: python test_coach.py"""
from coach import ROUTINES, next_weight, round_down, Session


def upper_day():
    """A session set up for 4 days a week, so today is Upper (Bench Press first)."""
    s = Session()
    s.handle("overview", days=4)
    return s


def test_maths():
    # Our worked example: 20 kg x 4, target 10 -> about 17.0 -> rounds down to 15
    assert next_weight(20, 4, 10) == 15
    # Hitting the target exactly keeps the same weight (checks the float fix)
    assert next_weight(70, 10, 10) == 70
    # More target reps than you managed must give a LOWER weight
    assert next_weight(60, 8, 10) < 60
    # Beating the target suggests going heavier
    assert next_weight(60, 12, 10) > 60
    assert round_down(17.0) == 15


def test_session_flow():
    s = upper_day()
    s.handle("set_done", weight=70, reps=8)
    assert s.set_number == 2
    assert s.current()["weight"] < 70          # weight was adjusted down

    s.handle("equipment_taken")
    assert s.current()["name"] == "Seated Chest Press"
    assert {"exercise": "Bench Press", "set": 2,
            "note": "swapped to Seated Chest Press"} in s.log

    s.handle("pain")
    assert s.current()["name"] == "Seated Cable Row"   # moved on after pain

    assert s.handle("set_done") == "How many reps did you get?"


def test_plausibility_check():
    s = upper_day()
    reply = s.handle("set_done", reps=60)
    assert reply == ("I heard 60 reps, that doesn't sound right. "
                     "How many reps did you get?")
    assert s.log == []                          # rejected: nothing logged

    s.handle("set_done", reps=8)
    assert len(s.log) == 1 and s.log[0]["reps"] == 8   # accepted


def test_undo():
    s = upper_day()
    assert s.handle("undo") == "There's nothing to undo."
    weight_before = s.current()["weight"]

    s.handle("set_done", weight=64, reps=8)
    assert len(s.log) == 1
    s.handle("undo")
    assert len(s.log) == 0                       # log is shorter again
    assert s.current()["weight"] == weight_before   # weight is back
    assert s.set_number == 1


def test_second_undo_has_nothing_to_undo():
    s = upper_day()
    s.handle("set_done", weight=64, reps=8)
    s.handle("undo")
    assert s.handle("undo") == "There's nothing to undo."


def test_undo_with_corrected_numbers():
    s = upper_day()
    s.handle("set_done", weight=64, reps=8)
    s.handle("undo", weight=60, reps=8)
    assert s.log == [{"exercise": "Bench Press", "set": 1, "weight": 60, "reps": 8}]


def test_no_routine_overview_asks_for_days():
    s = Session()
    assert s.routine is None
    assert s.handle("overview") == ("Let's set you up. "
                                    "How many days a week will you be training?")
    assert s.awaiting == "days"


def test_other_intent_before_routine_changes_nothing():
    s = Session()
    reply = s.handle("set_done", weight=40, reps=10)
    assert reply == "Say 'what workout should I do?' to set up your routine."
    assert s.awaiting is None and s.routine is None and s.log == []


def test_only_overview_starts_setup():
    s = Session()
    s.handle("unknown")                         # e.g. background talk
    s.handle("set_done", reps=6)                # a stray number
    assert s.routine is None and s.awaiting is None

    s.handle("overview")
    s.handle("unknown", days=5)                 # unknown never changes state
    assert s.routine is None and s.awaiting == "days"


def test_three_loads_the_three_day_routine():
    s = Session()
    s.handle("overview")
    reply = s.handle("set_done", reps=3)       # "three", heard as reps=3
    assert s.routine == ["Upper", "Lower", "Full Body"]
    assert s.today == "Upper" and s.awaiting is None
    assert s.log == []                           # not a logged set
    assert reply == ("3 days a week: Upper, Lower and Full Body. Today is Upper: "
                     "Bench Press, Seated Cable Row and Bicep Curl. "
                     "Say 'what's first' when you're ready.")


def test_seven_days_gives_six():
    s = Session()
    s.handle("overview")
    reply = s.handle("overview", days=7)
    assert s.routine == ROUTINES[6]
    assert reply.startswith("Seven days leaves no rest day, and beginners need "
                            "recovery, so I've set you up on 6. 6 days a week:")


def test_bad_number_asks_again():
    s = Session()
    s.handle("overview")
    assert s.handle("set_done", reps=12).startswith("Sorry, I need a number from 1 to 7.")
    assert s.handle("next").startswith("Sorry")  # no number at all
    assert s.awaiting == "days" and s.routine is None


def test_overview_with_routine():
    s = upper_day()
    assert s.handle("overview") == ("Today is Upper: Bench Press, Seated Cable Row "
                                    "and Bicep Curl. Say 'what's first' to start.")


def test_pain_before_routine():
    s = Session()
    reply = s.handle("pain")
    assert "rest today" in reply
    assert "days" not in reply and s.awaiting != "days"


def test_full_body_workout_can_be_completed():
    s = Session()
    s.handle("overview")
    s.handle("overview", days=1)
    assert s.handle("next").startswith("Squat, set 1 of 3")
    for _ in range(9):                           # 3 exercises x 3 sets
        reply = s.handle("set_done", reps=10)
    assert reply.endswith("That's the workout done. Nice work.")
    assert [entry["exercise"] for entry in s.log] == (
        ["Squat"] * 3 + ["Bench Press"] * 3 + ["Seated Cable Row"] * 3)


if __name__ == "__main__":
    tests = [f for name, f in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"All {len(tests)} coach tests passed")

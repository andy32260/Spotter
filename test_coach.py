"""Sanity tests for coach.py. Run: python test_coach.py"""
from coach import next_weight, round_down, Session


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
    s = Session()
    s.handle("set_done", weight=70, reps=8)
    assert s.set_number == 2
    assert s.current()["weight"] < 70          # weight was adjusted down

    s.handle("equipment_taken")
    assert s.current()["name"] == "Seated Chest Press"
    assert {"exercise": "Bench Press", "set": 2,
            "note": "swapped to Seated Chest Press"} in s.log

    s.handle("pain")
    assert s.current()["name"] == "Squat"      # moved on after pain

    assert s.handle("set_done") == "How many reps did you get?"


def test_plausibility_check():
    s = Session()
    reply = s.handle("set_done", reps=60)
    assert reply == ("I heard 60 reps, that doesn't sound right. "
                     "How many reps did you get?")
    assert s.log == []                          # rejected: nothing logged

    s.handle("set_done", reps=8)
    assert len(s.log) == 1 and s.log[0]["reps"] == 8   # accepted


def test_undo():
    s = Session()
    assert s.handle("undo") == "There's nothing to undo."
    weight_before = s.current()["weight"]

    s.handle("set_done", weight=64, reps=8)
    assert len(s.log) == 1
    s.handle("undo")
    assert len(s.log) == 0                       # log is shorter again
    assert s.current()["weight"] == weight_before   # weight is back
    assert s.set_number == 1


def test_second_undo_has_nothing_to_undo():
    s = Session()
    s.handle("set_done", weight=64, reps=8)
    s.handle("undo")
    assert s.handle("undo") == "There's nothing to undo."


def test_undo_with_corrected_numbers():
    s = Session()
    s.handle("set_done", weight=64, reps=8)
    s.handle("undo", weight=60, reps=8)
    assert s.log == [{"exercise": "Bench Press", "set": 1, "weight": 60, "reps": 8}]


if __name__ == "__main__":
    test_maths()
    test_session_flow()
    test_plausibility_check()
    test_undo()
    test_second_undo_has_nothing_to_undo()
    test_undo_with_corrected_numbers()
    print("All tests passed")
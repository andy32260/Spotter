"""Sanity tests for coach.py. Run: python test_coach.py"""
from coach import (FORM_CUES, ROUTINES, TEMPLATES, next_weight, round_down,
                   spoken_duration, Session)


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
    assert "first a light warm-up" in s.handle("next")
    assert s.handle("skip").endswith("Squat, set 1 of 3: 40 kilos for 10 reps.")
    for _ in range(9):                           # 3 exercises x 3 sets
        reply = s.handle("set_done", reps=10)
    assert reply == ("Workout done. You logged 9 sets across 3 exercises. "
                     "Next session: Full Body.")      # 1-day routine repeats
    assert [entry["exercise"] for entry in s.log] == (
        ["Squat"] * 3 + ["Bench Press"] * 3 + ["Seated Cable Row"] * 3)
    assert s.details == ["Squat: 3 sets, best 40 kg x 10",
                         "Bench Press: 3 sets, best 40 kg x 10",
                         "Seated Cable Row: 3 sets, best 35 kg x 10"]
    assert s.rest_seconds == 0


def test_rest_after_a_set():
    s = upper_day()
    reply = s.handle("set_done", reps=10)               # Bench Press: compound
    assert s.rest_seconds == 150 and reply.endswith("Rest 2 minutes 30 seconds.")

    s.handle("pain")                                    # pain never starts a rest
    assert s.rest_seconds == 0


def test_rest_for_bicep_curl():
    s = upper_day()
    for _ in range(6):                                  # Bench Press and Cable Row
        s.handle("set_done", reps=10)
    assert s.current()["name"] == "Bicep Curl"
    reply = s.handle("set_done", reps=10)
    assert s.rest_seconds == 90 and reply.endswith("Rest 1 minute 30 seconds.")


def test_spoken_duration():
    assert spoken_duration(150) == "2 minutes 30 seconds"
    assert spoken_duration(90) == "1 minute 30 seconds"
    assert spoken_duration(120) == "2 minutes"
    assert spoken_duration(45) == "45 seconds"


def test_no_rest_after_the_final_set():
    s = Session()
    s.handle("overview", days=1)
    for _ in range(9):
        reply = s.handle("set_done", reps=10)
    assert s.rest_seconds == 0 and "Rest" not in reply


def test_undo_with_numbers_starts_no_rest():
    s = upper_day()
    s.handle("set_done", reps=8)
    reply = s.handle("undo", weight=40, reps=10)
    assert s.rest_seconds == 0 and "Rest" not in reply


def test_every_exercise_has_a_form_cue():
    for day, exercises in TEMPLATES.items():
        for ex in exercises:
            for name in (ex["name"], ex["alternative"]["name"]):
                assert name in FORM_CUES, f"no form cue for {name} ({day})"


def test_form_cue():
    s = upper_day()
    reply = s.handle("form")
    assert reply.startswith("Bench Press: ") and "45 degrees" in reply
    assert reply.endswith("If anything feels sharp or painful, stop.")
    assert s.rest_seconds == 0 and s.log == []


def test_form_before_routine_changes_nothing():
    s = Session()
    assert s.handle("form") == "Say 'what workout should I do?' to set up your routine."
    assert s.routine is None and s.awaiting is None


def test_three_day_summary_names_the_next_day():
    s = upper_day_of(3)
    for _ in range(9):
        reply = s.handle("set_done", reps=10)
    assert "Workout done" in reply and "Next session: Lower." in reply


def test_workout_ending_with_pain():
    s = upper_day_of(1)                          # Full Body
    for _ in range(6):                           # Squat and Bench Press
        s.handle("set_done", reps=10)
    reply = s.handle("pain")                     # stop the last exercise
    assert "You stopped Seated Cable Row because of pain" in reply
    assert "Seated Cable Row: 0 sets (stopped: pain)" in s.details


def test_mid_workout_summary():
    s = upper_day_of(1)
    s.handle("set_done", reps=10)
    reply = s.handle("summary")
    assert reply == ("So far: 1 set across 1 exercise. "
                     "Next up: Squat, set 2 of 3: 40 kilos for 10 reps.")
    assert s.details is None                     # no summary card yet


def test_best_set_is_the_heaviest():
    s = upper_day_of(1)
    s.handle("set_done", weight=40, reps=10)
    s.handle("set_done", weight=50, reps=6)
    s.handle("set_done", weight=45, reps=10)
    _, details = s.summary()
    assert details[0] == "Squat: 3 sets, best 50 kg x 6"


def upper_day_of(days):
    """A session set up for the given days a week (today is day 1)."""
    s = Session()
    s.handle("overview", days=days)
    return s


def warmed_up(effort):
    """Upper day, warm-up done on Bench Press (planned 40 kg) with this effort."""
    s = upper_day()
    s.handle("next")
    s.handle("effort", effort=effort)
    return s


def test_warm_up_prompt():
    s = upper_day()
    reply = s.handle("next")
    assert reply == ("Bench Press: first a light warm-up. Do 10 reps with 20 kilos "
                     "and tell me how it felt: easy, about right or hard.")
    assert s.awaiting == "effort"


def test_warm_up_sets_the_working_weight():
    for effort, weight in [("easy", 40), ("right", 30), ("hard", 20)]:
        s = warmed_up(effort)
        assert s.current()["weight"] == weight, effort
        assert s.awaiting is None and s.rest_seconds == 0
        assert s.log == [{"exercise": "Bench Press", "note": f"warm-up: {effort}"}]


def test_warm_up_reply_and_asking_again():
    s = upper_day()
    s.handle("next")
    assert s.handle("set_done", reps=10) == "How did it feel: easy, about right or hard?"
    assert s.handle("effort", effort="right") == (
        "Got it. Working sets at 30 kilos. Bench Press, set 1 of 3: 30 kilos for 10 reps.")
    assert s.handle("next") == "Bench Press, set 1 of 3: 30 kilos for 10 reps."  # no second warm-up


def test_skip_warm_up():
    s = upper_day()
    s.handle("next")
    s.handle("skip")
    assert s.current()["weight"] == 40 and s.current()["calibrated"]
    assert s.log == [] and s.awaiting is None


def test_pain_during_warm_up():
    s = upper_day()
    s.handle("next")
    s.handle("pain")
    assert s.current()["name"] == "Seated Cable Row" and s.awaiting is None
    assert s.log == [{"exercise": "Bench Press", "set": 1, "note": "stopped: pain"}]


def test_undo_a_warm_up():
    s = warmed_up("hard")
    assert s.handle("undo") == "Undone. How did it feel: easy, about right or hard?"
    assert s.log == [] and s.awaiting == "effort" and s.current()["weight"] == 40
    s.handle("effort", effort="easy")
    assert s.current()["weight"] == 40


def test_warm_up_is_not_a_set():
    s = warmed_up("right")
    s.handle("set_done", reps=10)
    assert s.handle("summary").startswith("So far: 1 set across 1 exercise.")
    _, details = s.summary()
    assert details == ["Bench Press: 1 set, best 30 kg x 10 (warm-up: right)"]


def test_easy_set_goes_up():
    s = upper_day()                                   # Bench Press, target 10
    reply = s.handle("set_done", weight=40, reps=10, effort="easy")
    assert s.current()["weight"] == 42.5
    assert "Felt easy, so going up to 42.5 kilos." in reply


def test_hard_set_stays():
    s = upper_day()
    reply = s.handle("set_done", weight=40, reps=10, effort="hard")
    assert s.current()["weight"] == 40
    assert "Felt hard, so staying at 40 kilos." in reply


def test_effort_only_set():
    s = upper_day()
    s.handle("set_done", effort="easy")               # "that was way too easy"
    assert s.current()["weight"] == 42.5
    assert s.log == [{"exercise": "Bench Press", "set": 1, "weight": 40,
                      "reps": 10, "note": "effort: easy"}]


def test_no_nudge_when_target_missed():
    s = upper_day()
    reply = s.handle("set_done", weight=40, reps=7, effort="easy")
    assert s.current()["weight"] == next_weight(40, 7, 10)   # the normal Epley drop
    assert "Felt" not in reply


if __name__ == "__main__":
    tests = [f for name, f in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"All {len(tests)} coach tests passed")

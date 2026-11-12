"""
coach.py - the workout plan and the coaching rules.

There is NO AI in this file. The AI (in parser.py, built later) only turns
speech into an "intent" plus numbers. Everything the coach decides is plain
Python here, so it is consistent and easy to explain and test.
"""
import copy
import math

# The workout templates. Every exercise is 3 sets of 10 reps, with a starting
# weight (kg) and one alternative for when the equipment is taken.
# TODO
# Rest between sets, in seconds: longer for big compound lifts.
COMPOUND_LIFTS = {
    "Bench Press", "Squat", "Seated Cable Row", "Romanian Deadlift", "Lat Pulldown",
    "Dumbbell Row", "Dumbbell Shoulder Press", "Leg Press", "Seated Chest Press",
    "Machine Shoulder Press", "Goblet Squat",
}


def rest_for(name):
    return 150 if name in COMPOUND_LIFTS else 90


def spoken_duration(seconds):
    """150 -> '2 minutes 30 seconds', 90 -> '1 minute 30 seconds', 45 -> '45 seconds'."""
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds or not minutes:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return " ".join(parts)


def exercise(name, weight, alt_name, alt_weight):
    return {"name": name, "weight": weight, "reps": 10, "sets": 3,
            "rest": rest_for(name),
            "alternative": {"name": alt_name, "weight": alt_weight,
                            "rest": rest_for(alt_name)}}


LOWER = [
    exercise("Squat", 40, "Leg Press", 80),
    exercise("Romanian Deadlift", 40, "Lying Leg Curl", 25),
    exercise("Leg Extension", 25, "Goblet Squat", 12.5),
]

TEMPLATES = {
    "Full Body": [
        exercise("Squat", 40, "Leg Press", 80),
        exercise("Bench Press", 40, "Seated Chest Press", 30),
        exercise("Seated Cable Row", 35, "Dumbbell Row", 12.5),
    ],
    "Upper": [
        exercise("Bench Press", 40, "Seated Chest Press", 30),
        exercise("Seated Cable Row", 35, "Dumbbell Row", 12.5),
        exercise("Bicep Curl", 7.5, "Preacher Curl", 15),
    ],
    "Lower": LOWER,
    "Legs": LOWER,
    "Push": [
        exercise("Bench Press", 40, "Seated Chest Press", 30),
        exercise("Dumbbell Shoulder Press", 10, "Machine Shoulder Press", 20),
        exercise("Tricep Pushdown", 15, "Overhead Tricep Extension", 10),
    ],
    "Pull": [
        exercise("Lat Pulldown", 35, "Seated Cable Row", 35),
        exercise("Dumbbell Row", 12.5, "Seated Cable Row", 35),
        exercise("Bicep Curl", 7.5, "Preacher Curl", 15),
    ],
}

# The week's workouts, by how many days a week you train (7 is capped at 6).
ROUTINES = {
    1: ["Full Body"],
    2: ["Full Body", "Full Body"],
    3: ["Upper", "Lower", "Full Body"],
    4: ["Upper", "Lower", "Upper", "Lower"],
    5: ["Push", "Pull", "Legs", "Upper", "Lower"],
    6: ["Push", "Pull", "Legs", "Push", "Pull", "Legs"],
}

ASK_DAYS = "How many days a week will you be training?"


def and_list(items):
    """['A', 'B', 'C'] -> 'A, B and C'."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ---------- The maths (Epley formula) ----------

def estimate_max(weight, reps):
    """Estimate the heaviest weight you could lift once."""
    return weight * (1 + reps / 30)


def weight_for_reps(max_weight, target_reps):
    """Reverse Epley: the weight you should manage for target_reps."""
    return max_weight / (1 + target_reps / 30)


def round_down(weight, step=2.5):
    """Round DOWN to the nearest plate jump. Safer for beginners.
    round(weight, 6) first stops float errors like 69.9999999 -> 67.5."""
    return math.floor(round(weight, 6) / step) * step


def next_weight(weight, reps_done, target_reps):
    """The suggested weight for the next set."""
    max_weight = estimate_max(weight, reps_done)
    return round_down(weight_for_reps(max_weight, target_reps))


# ---------- The session (remembers where you are) ----------

class Session:
    def __init__(self):
        self.routine = None     # the week's workout names, once chosen
        self.today = None       # today's workout name, e.g. "Upper"
        self.plan = []          # today's exercises (copies, so weights can change)
        self.awaiting = None    # "days" while waiting for "how many days a week?"
        self.index = 0          # which exercise we are on
        self.set_number = 1     # which set of that exercise
        self.log = []           # everything that happened, shown on screen
        self.snapshot = None    # the state just before the last logged set
        self.rest_seconds = 0   # rest to take after this turn (0 = none)

    def current(self):
        if self.index < len(self.plan):
            return self.plan[self.index]
        return None             # workout finished

    def describe_current(self):
        if self.routine is None:
            return "No routine yet."
        ex = self.current()
        if ex is None:
            return "That's the workout done. Nice work."
        return (f"{ex['name']}, set {self.set_number} of {ex['sets']}: "
                f"{ex['weight']:g} kilos for {ex['reps']} reps.")

    def move_to_next_exercise(self):
        self.index += 1
        self.set_number = 1

    # One function per intent. handle() picks which one to run.
    def handle(self, intent, weight=None, reps=None, days=None):
        self.rest_seconds = 0   # only a successfully logged set starts a rest
        # Safety first: pain is handled in every state, even during setup.
        if intent == "pain":
            if self.routine is None:
                self.awaiting = None    # don't carry on asking about days
                return ("If something hurts before you've even started, rest "
                        "today and get it checked if it doesn't settle.")
            if self.current() is None:
                return ("That's the workout done. If something hurts, rest and "
                        "get it checked if it doesn't settle.")
            return self.pain()
        # "unknown" may just be background talk, so it never changes anything.
        # While waiting for "how many days a week?", any other number is the answer.
        if self.awaiting == "days" and intent != "unknown":
            return self.choose_days(days or reps or weight)
        if self.routine is None:
            if intent == "overview":    # the only way to start setting up
                self.awaiting = "days"
                return self.choose_days(days) if days else "Let's set you up. " + ASK_DAYS
            if self.awaiting == "days":
                return "Sorry, I need a number from 1 to 7. " + ASK_DAYS
            return "Say 'what workout should I do?' to set up your routine."
        if intent == "undo":    # before the "done" check, so the last set can be undone
            return self.undo(weight, reps)
        if intent == "overview":    # also works after the workout is finished
            return self.overview()
        if self.current() is None:
            return "That's the workout done. Nice work."
        if intent == "next":
            return self.describe_current()
        if intent == "set_done":
            return self.set_done(weight, reps)
        if intent == "pain":
            return self.pain()
        if intent == "equipment_taken":
            return self.equipment_taken()
        return "Sorry, I didn't catch that. Try: 'got 8 reps at 60 kilos'."

    def set_done(self, weight, reps):
        ex = self.current()
        if reps is None:
            return "How many reps did you get?"
        # Plausibility check: a mishearing must never end up in the log.
        if not 1 <= reps <= 30 or (weight is not None and not 1 <= weight <= 300):
            heard = f"I heard {reps} reps"
            if weight is not None:
                heard += f" at {weight:g} kilos"
            return heard + ", that doesn't sound right. How many reps did you get?"
        if weight is None:
            weight = ex["weight"]   # assume they used the planned weight

        # Save the state before changing anything, so "undo" can restore it.
        self.snapshot = (copy.deepcopy(self.plan), self.index,
                         self.set_number, len(self.log))
        new_weight = next_weight(weight, reps, ex["reps"])
        self.log.append({"exercise": ex["name"], "set": self.set_number,
                         "weight": weight, "reps": reps})
        ex["weight"] = new_weight

        # Repeat back what we heard, so mishearings in a noisy gym get caught.
        reply = f"Logged {weight:g} kilos for {reps}. "
        if self.set_number < ex["sets"]:
            self.set_number += 1
        else:
            self.move_to_next_exercise()
            reply += f"{ex['name']} done. "
        reply += "Next: " + self.describe_current()
        if self.current() is not None:  # no rest after the final set of the workout
            self.rest_seconds = ex["rest"]
            reply += f" Rest {spoken_duration(self.rest_seconds)}."
        return reply

    def pain(self):
        ex = self.current()
        self.log.append({"exercise": ex["name"], "set": self.set_number,
                         "note": "stopped: pain"})
        self.move_to_next_exercise()
        return (f"Stopping {ex['name']}. If the pain is sharp or doesn't go "
                f"away, stop training and get it checked. "
                f"Next: {self.describe_current()}")

    def equipment_taken(self):
        ex = self.current()
        alt = ex.pop("alternative", None)   # pop: each alternative used once
        if alt is None:
            self.move_to_next_exercise()
            return (f"No other option for {ex['name']}, so we'll skip it. "
                    f"Next: {self.describe_current()}")
        self.log.append({"exercise": ex["name"], "set": self.set_number,
                         "note": f"swapped to {alt['name']}"})
        ex["name"], ex["weight"], ex["rest"] = alt["name"], alt["weight"], alt["rest"]
        return f"No problem, switch to {self.describe_current()}"

    def choose_days(self, days):
        if days is None or days != int(days) or not 1 <= days <= 7:
            return "Sorry, I need a number from 1 to 7. " + ASK_DAYS
        days, note = int(days), ""
        if days == 7:
            days = 6
            note = ("Seven days leaves no rest day, and beginners need recovery, "
                    "so I've set you up on 6. ")
        self.awaiting = None
        self.routine = ROUTINES[days]
        self.today = self.routine[0]    # today is day 1 of the week
        self.plan = [dict(ex) for ex in TEMPLATES[self.today]]
        return (note + f"{days} days a week: {and_list(self.routine)}. "
                f"Today is {self.today}: {self.todays_exercises()}. "
                "Say 'what's first' when you're ready.")

    def todays_exercises(self):
        return and_list([ex["name"] for ex in self.plan])

    def overview(self):
        return (f"Today is {self.today}: {self.todays_exercises()}. "
                "Say 'what's first' to start.")

    def undo(self, weight, reps):
        if self.snapshot is None:
            return "There's nothing to undo."
        self.plan, self.index, self.set_number, log_length = self.snapshot
        self.snapshot = None              # one undo per set: a second undo has nothing left
        del self.log[log_length:]         # remove entries added since the snapshot
        if reps is not None:              # "no, it was 60 for 8": log the fix
            reply = self.set_done(weight, reps)
            if self.rest_seconds:         # a correction never starts a rest
                reply = reply.removesuffix(f" Rest {spoken_duration(self.rest_seconds)}.")
                self.rest_seconds = 0
            return "Undone. " + reply
        return "Undone. " + self.describe_current()


# ---------- Typed test mode (no voice, no AI yet) ----------
# Run: python coach.py
# Type:  next | done 60 8 | done 8 | pain | taken | quit
if __name__ == "__main__":
    session = Session()
    print(session.describe_current())
    while True:
        words = input("> ").strip().lower().split()
        if not words or words[0] == "quit":
            break
        command = words[0]
        if command == "done":
            numbers = [float(w) for w in words[1:]]
            if len(numbers) == 2:
                print(session.handle("set_done", weight=numbers[0], reps=int(numbers[1])))
            elif len(numbers) == 1:
                print(session.handle("set_done", reps=int(numbers[0])))
            else:
                print(session.handle("set_done"))
        elif command == "taken":
            print(session.handle("equipment_taken"))
        else:
            print(session.handle(command))
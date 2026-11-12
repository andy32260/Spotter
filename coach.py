"""
coach.py - the workout plan and the coaching rules.

There is NO AI in this file. The AI (in parser.py, built later) only turns
speech into an "intent" plus numbers. Everything the coach decides is plain
Python here, so it is consistent and easy to explain and test.
"""
import copy
import math

# The workout plan. Each exercise has a starting weight (kg), target reps,
# number of sets and one alternative for when the equipment is taken.
# TODO 
PLAN = [
    {"name": "Bench Press", "weight": 40, "reps": 10, "sets": 3,
     "alternative": {"name": "Seated Chest Press", "weight": 30}},
    {"name": "Squat", "weight": 40, "reps": 10, "sets": 3,
     "alternative": {"name": "Leg Press", "weight": 80}},
    {"name": "Bicep Curl", "weight": 7.5, "reps": 10, "sets": 3,
     "alternative": {"name": "Preacher Curl", "weight": 15}},
]


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
    def __init__(self, plan=PLAN):
        # Copy each exercise so changing weights never edits the original PLAN.
        self.plan = [dict(exercise) for exercise in plan]
        self.index = 0          # which exercise we are on
        self.set_number = 1     # which set of that exercise
        self.log = []           # everything that happened, shown on screen
        self.snapshot = None    # the state just before the last logged set

    def current(self):
        if self.index < len(self.plan):
            return self.plan[self.index]
        return None             # workout finished

    def describe_current(self):
        ex = self.current()
        if ex is None:
            return "That's the workout done. Nice work."
        return (f"{ex['name']}, set {self.set_number} of {ex['sets']}: "
                f"{ex['weight']:g} kilos for {ex['reps']} reps.")

    def move_to_next_exercise(self):
        self.index += 1
        self.set_number = 1

    # One function per intent. handle() picks which one to run.
    def handle(self, intent, weight=None, reps=None):
        if intent == "undo":    # before the "done" check, so the last set can be undone
            return self.undo(weight, reps)
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
        return reply + "Next: " + self.describe_current()

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
        ex["name"], ex["weight"] = alt["name"], alt["weight"]
        return f"No problem, switch to {self.describe_current()}"

    def undo(self, weight, reps):
        if self.snapshot is None:
            return "There's nothing to undo."
        self.plan, self.index, self.set_number, log_length = self.snapshot
        self.snapshot = None              # one undo per set: a second undo has nothing left
        del self.log[log_length:]         # remove entries added since the snapshot
        if reps is not None:              # "no, it was 60 for 8": log the fix
            return "Undone. " + self.set_done(weight, reps)
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
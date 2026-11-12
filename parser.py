"""Turn what the user said into an intent plus an optional weight and reps.

parse() tries an AI model (on Groq) first and falls back to the rule-based
parse_regex(), so the coach keeps working with no key, no internet or a bad
AI answer.
"""
import json
import os
import re

from groq import Groq

INTENTS = ["next", "set_done", "pain", "equipment_taken", "undo", "unknown"]
PAIN_WORDS = [
    "hurt", "pain", "sore", "twinge", "injur", "killing", "ache", "aching",
    "tweak", "tweaked", "pulled", "strain", "agony", "can't move",
]

NUMBER_WORDS = [
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
]

# Checked in this order: the first group with a matching word wins.
INTENT_WORDS = [
    ("pain", PAIN_WORDS),
    ("undo", ["undo", "wrong", "scratch that", "not right", "didn't say"]),
    ("equipment_taken", ["taken", "busy", "in use", "occupied", "someone on"]),
    ("next", ["next", "what now", "ready", "start"]),
]

# A number, optionally followed by a unit: "60kg", "60 kilos", "8 reps", "8".
NUMBER_WITH_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(kgs?|kilos?|reps?)?\b")

LLM_INSTRUCTION = """You read what a beginner says to their gym coach.
Return JSON with "intent", "weight" (kg) and "reps".
intent is one of: next, set_done, pain, equipment_taken, undo, unknown.
Use undo when the user says the last set was recorded wrong; include the
corrected weight and reps if they said them.
Only extract what the user said. Never guess or invent numbers.
Use null for weight or reps when the user didn't say them or you are unsure.

Examples:
"ugh that was rough, managed about 6" -> {"intent": "set_done", "weight": null, "reps": 6}
"did sixty for eight" -> {"intent": "set_done", "weight": 60, "reps": 8}
"someone's on the bench" -> {"intent": "equipment_taken", "weight": null, "reps": null}
"what am I doing now" -> {"intent": "next", "weight": null, "reps": null}
"no that's wrong, it was 60 kilos 8 reps" -> {"intent": "undo", "weight": 60, "reps": 8}"""

def parse(text):
    # Safety override: pain is caught by plain keywords, never left to the AI.
    if any(word in text.lower() for word in PAIN_WORDS):
        return {"intent": "pain", "weight": None, "reps": None, "source": "regex"}

    if not os.getenv("GROQ_API_KEY"):
        reason = "no key"
    elif not os.getenv("GROQ_MODEL"):
        reason = "no model (set GROQ_MODEL in .env)"
    else:
        try:
            return {**validated(parse_llm(text)), "source": "ai"}
        except Exception as error:  # any failure at all: use the regex instead
            reason = fallback_reason(error)

    print(f"Using regex instead of AI: {reason}", flush=True)
    return {**parse_regex(text), "source": "regex"}


def fallback_reason(error):
    """A short, readable reason for the terminal, e.g. 'timeout (ReadTimeout: ...)'."""
    detail = f"{type(error).__name__}: {error}"
    if "timeout" in type(error).__name__.lower():
        return f"timeout ({detail})"
    if isinstance(error, (ValueError, KeyError)):  # bad JSON or failed validated()
        return f"invalid result ({detail})"
    return detail


def parse_llm(text):
    """Ask the AI model to read the sentence. Returns its raw (unchecked) JSON."""
    # max_retries=0: the SDK retries twice by default, which would turn our
    # 4 second limit into 12+ seconds of waiting.
    client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=4.0, max_retries=0)
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL"),
        messages=[
            {"role": "system", "content": LLM_INSTRUCTION},
            {"role": "user", "content": text},
        ],
        temperature=0,
        response_format={"type": "json_object"},  # must reply with valid JSON
    )
    return json.loads(response.choices[0].message.content)


def validated(result):
    """Never trust the AI's output blindly: raise ValueError if it's malformed."""
    intent, weight, reps = result["intent"], result["weight"], result["reps"]
    if intent not in INTENTS:
        raise ValueError(f"unknown intent {intent!r}")
    for value in (weight, reps):
        # bool is excluded because Python treats True as the number 1.
        if value is not None and (isinstance(value, bool)
                                  or not isinstance(value, (int, float))):
            raise ValueError(f"not a number: {value!r}")
    return {
        "intent": intent,
        "weight": None if weight is None else float(weight),
        "reps": None if reps is None else int(reps),
    }


def words_to_digits(text):
    """'got eight' -> 'got 8'. Word boundaries stop 'one' matching inside 'someone'."""
    for value, word in enumerate(NUMBER_WORDS, start=1):
        text = re.sub(rf"\b{word}\b", str(value), text)
    return text


def parse_regex(text):
    text = words_to_digits(text.lower())
    weight, reps = extract_numbers(text)

    for intent, words in INTENT_WORDS:
        if any(word in text for word in words):
            if intent == "undo":    # "scratch that, 60 for 8" keeps its numbers
                return {"intent": "undo", "weight": weight, "reps": reps}
            return {"intent": intent, "weight": None, "reps": None}

    if weight is None and reps is None:
        return {"intent": "unknown", "weight": None, "reps": None}
    return {"intent": "set_done", "weight": weight, "reps": reps}


def extract_numbers(text):
    """Find the weight and reps in text. Either can be None."""
    weight, reps, bare = None, None, []
    for number, unit in NUMBER_WITH_UNIT.findall(text):
        if unit.startswith("k"):
            weight = float(number)
        elif unit.startswith("r"):
            reps = int(float(number))
        else:
            bare.append(number)

    # Numbers without a unit fill the gaps: "60 for 8" is weight then reps,
    # and a single bare number ("got 8") is the reps.
    if len(bare) >= 2 and weight is None and reps is None:
        weight, reps = float(bare[0]), int(float(bare[1]))
    elif bare and reps is None:
        reps = int(float(bare[0]))
    elif bare and weight is None:
        weight = float(bare[0])

    return weight, reps

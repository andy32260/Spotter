"""Turn what the user said into an intent plus an optional weight and reps.

parse() tries an AI model (on Groq) first and falls back to the rule-based
parse_regex(), so the coach keeps working with no key, no internet or a bad
AI answer.
"""
import json
import os
import re

from groq import Groq

INTENTS = ["next", "set_done", "pain", "equipment_taken", "undo", "overview",
           "form", "summary", "unknown"]
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
    ("summary", ["how did i do", "summary", "recap", "how am i doing"]),
    ("form", ["how do i", "how should i", "form", "technique", "tips", "cues"]),
    ("overview", ["what workout", "what exercises", "routine", "plan"]),
    ("equipment_taken", ["taken", "busy", "in use", "occupied", "someone on"]),
    ("next", ["next", "what now", "ready", "start", "first"]),
]

# A number, optionally followed by a unit: "60kg", "60 kilos", "8 reps",
# "3 days", "8".
NUMBER_WITH_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(kgs?|kilos?|reps?|days?)?\b")

LLM_INSTRUCTION = """You read what a beginner says to their gym coach.
Return JSON with "intent", "weight" (kg), "reps" and "days" (days a week).
intent is one of: next, set_done, pain, equipment_taken, undo, overview, form, summary, unknown.
Use form when the user asks how to do the exercise or for technique tips.
Use summary when the user asks how their workout is going or for a recap.
Use overview when the user asks what workout or exercises they should do,
or says how many days a week they can train.
Use undo when the user says the last set was recorded wrong; include the
corrected weight and reps if they said them.
Only extract what the user said. Never guess or invent numbers.
Use null for weight, reps or days when the user didn't say them or you are unsure.

Examples:
"ugh that was rough, managed about 6" -> {"intent": "set_done", "weight": null, "reps": 6, "days": null}
"did sixty for eight" -> {"intent": "set_done", "weight": 60, "reps": 8, "days": null}
"someone's on the bench" -> {"intent": "equipment_taken", "weight": null, "reps": null, "days": null}
"what am I doing now" -> {"intent": "next", "weight": null, "reps": null, "days": null}
"what workout should I do" -> {"intent": "overview", "weight": null, "reps": null, "days": null}
"how am I meant to do this" -> {"intent": "form", "weight": null, "reps": null, "days": null}
"any tips for this one" -> {"intent": "form", "weight": null, "reps": null, "days": null}
"how's my workout going" -> {"intent": "summary", "weight": null, "reps": null, "days": null}
"I can train three days a week" -> {"intent": "overview", "weight": null, "reps": null, "days": 3}
"no that's wrong, it was 60 kilos 8 reps" -> {"intent": "undo", "weight": 60, "reps": 8, "days": null}"""

def parse(text):
    # Safety override: pain is caught by plain keywords, never left to the AI.
    if any(word in text.lower() for word in PAIN_WORDS):
        return {"intent": "pain", "weight": None, "reps": None, "days": None,
                "source": "regex"}

    if not os.getenv("GROQ_API_KEY"):
        reason = "no key"
    elif not os.getenv("GROQ_MODEL"):
        reason = "no model (set GROQ_MODEL in .env)"
    else:
        try:
            result = only_said_numbers(validated(parse_llm(text)), text)
            if result["intent"] == "unknown" and result["days"] is not None:
                result["intent"] = "overview"   # "3 days a week" answers the setup question
            return {**result, "source": "ai"}
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
    intent, weight, reps, days = (result["intent"], result["weight"],
                                  result["reps"], result["days"])
    if intent not in INTENTS:
        raise ValueError(f"unknown intent {intent!r}")
    for value in (weight, reps, days):
        # bool is excluded because Python treats True as the number 1.
        if value is not None and (isinstance(value, bool)
                                  or not isinstance(value, (int, float))):
            raise ValueError(f"not a number: {value!r}")
    return {
        "intent": intent,
        "weight": None if weight is None else float(weight),
        "reps": None if reps is None else int(reps),
        "days": None if days is None else int(days),
    }


def only_said_numbers(result, text):
    """The AI can invent numbers (e.g. days: 6 for "what workout should I do").
    Keep each number only if the user actually said it; otherwise use null."""
    said = numbers_said(text)
    for key in ("weight", "reps", "days"):
        if result[key] is not None and float(result[key]) not in said:
            print(f"[guard] dropped {key}={result[key]}: not said in {text!r}", flush=True)
            result[key] = None
    return result


def numbers_said(text):
    """Every number in text, as digits or words one to thirty: 'six or 7' -> {6.0, 7.0}."""
    text = re.sub(r"\btwenty[- ](one|two|three|four|five|six|seven|eight|nine)\b",
                  lambda m: str(21 + NUMBER_WORDS.index(m.group(1))), text.lower())
    text = re.sub(r"\bthirty\b", "30", words_to_digits(text))
    return {float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)}


def words_to_digits(text):
    """'got eight' -> 'got 8'. Word boundaries stop 'one' matching inside 'someone'."""
    for value, word in enumerate(NUMBER_WORDS, start=1):
        text = re.sub(rf"\b{word}\b", str(value), text)
    return text


def parse_regex(text):
    text = words_to_digits(text.lower())
    weight, reps, days = extract_numbers(text)

    for intent, words in INTENT_WORDS:
        if any(word in text for word in words):
            if intent == "undo":    # "scratch that, 60 for 8" keeps its numbers
                return {"intent": "undo", "weight": weight, "reps": reps, "days": days}
            return {"intent": intent, "weight": None, "reps": None, "days": days}

    if weight is None and reps is None:
        # "3 days a week" answers the setup question; anything else is unknown.
        intent = "overview" if days is not None else "unknown"
        return {"intent": intent, "weight": None, "reps": None, "days": days}
    return {"intent": "set_done", "weight": weight, "reps": reps, "days": days}


def extract_numbers(text):
    """Find the weight, reps and days a week in text. Any can be None."""
    weight, reps, days, bare = None, None, None, []
    for number, unit in NUMBER_WITH_UNIT.findall(text):
        if unit.startswith("k"):
            weight = float(number)
        elif unit.startswith("r"):
            reps = int(float(number))
        elif unit.startswith("d"):
            days = int(float(number))
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

    return weight, reps, days

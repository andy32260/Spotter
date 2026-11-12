# Gym Coach: a hands-free voice coach

## What it is

A hands-free voice coach for gym beginners: you tell it how your set went, in your own words, and it talks back. It adjusts the weight for your next set from what you describe, so you always know what to lift next without touching your phone.

## Requirements

- Python 3.10 or newer (tested on Python 3.13)
- Google Chrome or Microsoft Edge, which provide the Web Speech API used for listening and speaking
- A microphone
- A free Groq API key from https://console.groq.com/keys (optional: without one, the app still works using its built-in rules)

## Setup

Open a terminal in the project folder, then follow the steps for your system.

### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

If PowerShell refuses to run `Activate.ps1`, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Mac and Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Add your key

Open `.env` and paste your Groq key after `GROQ_API_KEY=`:

```
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

`.env` is listed in `.gitignore`, so your key is never committed.

## Run

With the virtual environment active, from the project folder:

```
python app.py
```

Then open http://127.0.0.1:5000 in Chrome or Edge and allow microphone access.

The terminal shows whether your key was found (never the key itself) and which model is used. Whenever the AI is not used for a sentence, it prints one line saying why, for example `Using regex instead of AI: no key`.

## How to use

**Tap to talk.** Tap the big button, say one sentence, and the coach answers out loud.

**Hands-free mode.** Press "Hands-free: OFF" to switch it on. The app now listens all the time, but only acts on sentences that start with the wake word "coach" or "hey coach", for example "coach, 60 kilos 8 reps". Anything else is shown as "Ignored (no wake word)". The microphone pauses while the coach is speaking, so it never hears itself. Tap to talk is disabled while hands-free mode is on.

**Follow-up window.** When the coach asks you a question, such as "How many reps did you get?", you can answer without the wake word for 8 seconds after it finishes speaking. The status line then shows "Listening for your answer...". One answer closes the window.

**Typing.** The text box does the same as speaking, which is handy for testing.

**Example phrases:**

| You say | What happens |
|---|---|
| "what's next" | The coach reads out your current exercise, set, weight and reps |
| "60 kilos 8 reps" | The set is logged and the next weight is worked out |
| "the bench is taken" | You are switched to the alternative exercise |
| "my shoulder hurts" | The exercise is stopped, with advice to get pain checked |
| "scratch that" or "undo" | The last logged set is removed |
| "no that's wrong, it was 60 kilos 8 reps" | The last set is removed and the corrected one is logged |

## How it works

```
speech (browser) -> parser.py -> coach.py -> spoken reply (browser)
```

1. The browser turns your speech into text and sends it to the server.
2. `parser.py` works out what you meant: an intent (such as "set done" or "pain") plus any weight and reps.
   - Pain is checked first with plain keyword rules, so a safety stop never depends on the AI.
   - Otherwise an AI model on Groq reads the sentence. Its answer is checked, and if anything goes wrong (no key, no internet, a timeout after 4 seconds, or an invalid answer), the app falls back to its own regex rules.
3. `coach.py` makes every decision: logging the set, working out the next weight, moving on, swapping equipment and undoing. It contains no AI, so its behaviour is predictable and fully tested.
4. The reply is shown on the page and spoken aloud by the browser.

The next weight comes from the Epley formula: it estimates the most you could lift once from what you just did, then works back to the weight you should manage for the target reps, rounded down to the nearest 2.5 kg. Implausible numbers (outside 1 to 30 reps or 1 to 300 kg) are never logged; the coach asks again instead.

### What each file does

| File | Purpose |
|---|---|
| `app.py` | Small Flask web server. Serves the page and passes each sentence through the parser and the coach. |
| `parser.py` | Turns a sentence into an intent, weight and reps (AI on Groq, with a regex fallback). |
| `coach.py` | The workout plan, the weight maths and the `Session` that remembers where you are. |
| `static/index.html` | The page layout. |
| `static/app.js` | Listening, speaking, hands-free mode, the wake word and the follow-up window. |
| `static/style.css` | High-contrast, large-text styling, readable at arm's length. |
| `test_coach.py`, `test_parser.py` | The tests. |
| `.env.example` | Template for your `.env` settings. |

## Running the tests

With the virtual environment active:

```
python test_coach.py
python test_parser.py
```

The tests never call the internet, even when your `.env` contains a key.

## Known limitations

- Works in Chrome and Edge only, because other browsers lack the speech recognition it needs.
- Needs an internet connection: Chrome and Edge send your speech to an online service to turn it into text, and the AI runs on Groq.
- Keeps one workout session in memory, so it is meant for one person at a time, and restarting the server starts a new workout.
- Speech recognition can mishear numbers, for example "for" as "4", or the wake word "coach" as "couch". The coach always repeats back what it logged, so mistakes are easy to catch and undo.
- The pain check deliberately errs on the side of caution, so phrases like "I pulled 140" or "no strain" also count as pain and stop the exercise.

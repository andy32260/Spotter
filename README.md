# Gym Coach: a hands-free voice coach

## What it is

Gym Coach is a voice coach that runs in your browser: it sets up a weekly routine for you, tells you what to lift, and adjusts the weight for your next set from how you describe the one you just did. You talk to it in your own words between sets, and it talks back, so you never need to touch your phone mid-workout.

It is made for gym beginners who want a simple plan, sensible weights, rest times and form reminders without having to learn an app.

## Requirements

- Python 3.10 or newer (tested on Python 3.13)
- Google Chrome or Microsoft Edge, which provide the speech recognition and speech output the app uses
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

Open `.env` and paste your Groq key after `GROQ_API_KEY=`. Leave the model as it is:

```
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

`.env` is listed in `.gitignore`, so your key is never committed. If you skip this step, the app runs on its built-in rules instead of the AI.

## Run

With the virtual environment active, from the project folder:

```
python app.py
```

Then open http://127.0.0.1:5000 in Chrome or Edge and allow microphone access.

The terminal shows whether your key was found (never the key itself) and which model is used. Whenever the AI is not used for a sentence, it prints one line saying why, for example `Using regex instead of AI: no key`.

## How to use

Press **Hands-free** to talk without touching anything, or **Tap to talk** to say one sentence at a time. You can also type into the box. The hint under the workout card always shows what to say next.

A typical session:

1. **"What workout should I do?"** The coach asks how many days a week you will train.
2. **"Three"** (any number from 1 to 7). The coach sets up your week and names today's workout:

   | Days a week | Your week |
   |---|---|
   | 1 | Full Body |
   | 2 | Full Body, Full Body |
   | 3 | Upper, Lower, Full Body |
   | 4 | Upper, Lower, Upper, Lower |
   | 5 | Push, Pull, Legs, Upper, Lower |
   | 6 | Push, Pull, Legs, Push, Pull, Legs |
   | 7 | The 6-day plan, because beginners need at least one rest day |

3. **"What's first?"** The coach reads out the exercise, the set and the weight, for example "Bench Press, set 1 of 3: 40 kilos for 10 reps."
4. **Describe each set:** "40 kilos, 10 reps", or just "only got 7" (the planned weight is assumed). The coach repeats back what it logged and works out the weight for your next set. Numbers that don't make sense (outside 1 to 30 reps or 1 to 300 kg) are never logged; the coach asks again.
5. **Rest timer.** After each set a countdown appears: 2 minutes 30 seconds for big compound lifts, 1 minute 30 seconds for everything else. The coach says "Ten seconds." near the end and "Time's up, go again." at zero. Saying anything else to the coach stops the timer.
6. **"How do I do this?"** The coach reads out short form cues for the current exercise.
7. **"The bench is taken."** You switch to that exercise's alternative (each alternative can be used once).
8. **"My shoulder hurts."** The coach stops that exercise, tells you to get sharp or lasting pain checked, and moves on. Pain is always handled, even before you have a routine.
9. **"Scratch that"** or **"undo".** The last logged set is removed, along with anything that happened after it (such as a swap). You can correct it in one go: "no, it was 40 kilos, 8 reps".
10. **"How did I do?"** Mid-workout you hear your progress so far. When the last set is logged, the coach reads a short summary automatically and a **Workout summary** card shows every exercise with its sets and best set.

**New session** (in Settings) clears everything and starts again from step 1.

## Settings

- **Hands-free** (the big button): the microphone listens all the time. It pauses while the coach is speaking, so it doesn't hear itself (unless Interrupt by voice is on).
- **Wake word** (default off): when on, the coach only acts on sentences that start with "coach" or "hey coach", for example "coach, 40 kilos 10 reps". After the coach asks you a question, you can answer without the wake word for 8 seconds. When off, the coach acts on everything it hears but ignores sentences it doesn't understand, which filters out most background chat.
- **Voice** on or off: when off, replies are shown as text only. **Coach's voice** lets you pick a voice. Edge has the most natural-sounding ones (for example "Microsoft Sonia Online (Natural)") and picks one automatically; Chrome usually picks "Google UK English Female".
- **Interrupt by voice** (default off): when on with hands-free, you can talk over the coach to cut it short. It works best with headphones, so the microphone doesn't pick up the coach's own voice.
- **Stop** (top of the screen, while the coach is speaking) or the **Esc** key: stops the coach mid-sentence.

Settings are remembered in your browser.

## How it works

```
your speech -> browser speech recognition -> parser.py -> coach.py -> spoken reply + screen
```

1. The browser turns your speech into text and sends it to the server.
2. `parser.py` works out what you meant: an intent (such as "set done", "pain" or "undo") plus any weight, reps or days per week.
   - Pain is checked first with plain keyword rules, so a safety stop never depends on the AI.
   - Otherwise an AI model on Groq reads the sentence. Its answer is checked, and any number it returns is kept only if that number actually appears in what you said, so the AI cannot invent weights, reps or days.
   - If anything goes wrong (no key, no internet, a timeout after 4 seconds, or an invalid answer), the parser falls back to its own regex rules.
3. `coach.py` makes every decision: the routine, the weight maths, rest times, form cues, swaps, undo and the summary. It contains no AI, so its behaviour is predictable and fully tested. Form cues are fixed, reviewed text.
4. The reply is spoken by the browser and shown on the page.

The next weight comes from the Epley formula: it estimates the most you could lift once from the set you just did, then works back to the weight you should manage for the target reps, rounded down to the nearest 2.5 kg.

### Files

| File | Purpose |
|---|---|
| `app.py` | Small Flask web server: serves the page and passes each sentence through the parser and the coach. |
| `parser.py` | Turns a sentence into an intent and numbers (AI on Groq, checked, with a regex fallback). |
| `coach.py` | The workouts, routines, weight maths, rest times, form cues and the `Session` that remembers where you are. |
| `static/index.html` | The page layout. |
| `static/app.js` | Listening, speaking, hands-free mode, the wake word, the rest timer and updating the page. |
| `static/style.css` | Dark, high-contrast styling, readable at arm's length. |
| `test_coach.py` | Tests for the coaching logic. |
| `test_parser.py` | Tests for the parser (they never call the internet). |
| `requirements.txt` | The Python packages to install. |
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
- Keeps one session in memory, for one person at a time. Nothing is saved, so restarting the server or pressing New session loses the workout.
- Speech recognition can mishear numbers, for example "for" as "4". The coach always repeats back what it logged, so mistakes are easy to catch and undo.
- With the wake word off, background speech that contains numbers can be logged as a set. The coach repeats it back, and "undo" removes it.
- The built-in rules match keywords, so a few phrases can be misread (for example "performed" contains "form"). The AI path handles these better.
- Form cues are general reminders for common exercises, not personal coaching. If anything feels sharp or painful, stop.

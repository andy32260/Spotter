# How I used AI tools

I used AI throughout this project, in three roles. I made the product decisions, tested every feature by hand and checked that I could explain each change before moving on.

## Tools

| Tool | What I used it for |
|---|---|
| Claude (claude.ai project chat) | Choosing and challenging the idea, checking existing products and guidelines, the design plan, writing one build prompt per feature and reviewing my test results |
| Claude Code | Writing and editing the code in my repo, one feature per prompt, then running the tests and starting the app before reporting back |
| Groq API (`GROQ_MODEL` in `.env`) | Inside the app: turns what the user says into an intent plus numbers |

## How the work was split

1. **Idea.** I pitched a live scam-call coach first. Claude checked and found Hiya AI Phone already does real-time scam alerts, so I dropped it. I then rejected a tyre-change coach (I can't drive, so I couldn't test it) and settled on a gym coach. A search showed voice gym loggers already exist, so I narrowed it to beginners, whose problem is knowing what to do, not logging.
2. **Design rules I set.** The AI only extracts the intent and numbers. All coaching decisions (routines, weight maths, rest times, form cues, safety) live in plain Python in `coach.py`, so they are consistent, testable and explainable. Pain is always checked by simple word rules first, so safety never depends on the AI alone.
3. **Build loop.** For each feature: Claude wrote a prompt from the design plan, Claude Code built it, I tested it by speaking to it in Chrome or Edge and reported what happened, and we fixed what I found. I committed after each working feature.

## Decisions where I checked the AI or the AI checked me

- **Weight maths:** the Epley formula, always rounded down to 2.5 kg for beginners. I worked an example by hand first so I could explain it.
- **Routines:** I chose the split for each number of training days. Claude pushed back on 7 days a week for a beginner, so the coach now explains that a rest day matters and uses the 6-day routine.
- **Rest times:** I wanted 2:30 to 3 minutes. Claude checked the guidance (2 to 3 minutes for heavy compound lifts, 1 to 2 for assistance exercises), so compounds rest 2:30 and isolation exercises 90 seconds.
- **Form cues:** Claude drafted short cues for all 17 exercises and I reviewed them. They are fixed text, not AI-generated, so the coach can't invent unsafe technique advice.
- **Accessibility:** Claude researched WCAG 2.2 and dark-theme guidance; the layout uses 4.5:1 text contrast, 44px+ targets, status shown in words (not colour alone) and a screen-reader announcement of the coach's reply.

## What testing found (and the AI did not)

- **Floating point bug:** hitting your target exactly (70 kg x 10) suggested 67.5 kg because 69.9999 rounded down. Fixed and covered by a test.
- **Impossible numbers:** I said "60 reps" on purpose and it was logged. Added a plausibility check that asks again instead.
- **Speech recognition error:** "60 for 8" was transcribed as "648" ("for" sounds like "4"). No parser can fix text that is already wrong, so I changed the voice design: the coach repeats back what it heard, the UI suggests saying "kilos" and "reps" and a spoken "undo" or "scratch that" corrects the last set.
- **A silent fallback:** the first AI parser (Gemini) never actually ran; every call failed and quietly fell back to regex. The "Understood by" label exposed it. I added logging of the fallback reason and switched to Groq, which only meant changing one function.
- **The AI inventing numbers:** a routine sometimes loaded without asking how many days. Now any number the AI returns is kept only if it appears in what was actually said.
- **Pain gaps:** "my elbow is killing me" was caught by the AI but not the safety rules, and pain was ignored before a routine existed. Both fixed so pain is handled first, in every state, without relying on the AI.
- **Hands-free follow-ups:** answering the coach's own question ("How many reps?") was ignored without the wake word. Added an 8 second follow-up window, then fixed a bug where it did not expire.
- **Empty transcripts:** with the wake word off, silence produced empty results that quietly changed the coach's state. Empty results are now ignored, and only "what workout should I do?" can start the setup.
- **Barge-in:** a Stop button and Esc cut the coach off. Optional "interrupt by voice" uses an echo filter so the coach doesn't react to its own voice through the speakers.

## What I checked myself

- Ran `test_coach.py` and `test_parser.py` after every change (tests never call the network)
- Tested every voice moment by speaking, including deliberate bad input and background audio
- Read each change and the agent's plain-English explanation before moving on
- Kept the API key in `.env`, which is in `.gitignore`, and checked `git status` before every commit
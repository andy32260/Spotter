const $ = (id) => document.getElementById(id);
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

let handsFreeOn = false;
let handsFree = null;  // the always-listening recogniser (set up below)
let speaking = null;   // the reply currently being read out, if any

// Settings are remembered in this browser. Storage can be blocked (e.g. private
// windows), so every read and write is wrapped and falls back quietly.
const settings = {
  load(key, fallback) {
    try { return localStorage.getItem("coach." + key) ?? fallback; } catch (e) { return fallback; }
  },
  save(key, value) {
    try { localStorage.setItem("coach." + key, value); } catch (e) { /* not saved: fine */ }
  },
};

// An ON/OFF button that remembers its state. Returns a function to read it.
function toggle(id, label, key, defaultOn, onChange) {
  let on = settings.load(key, defaultOn ? "on" : "off") === "on";
  const show = () => {
    $(id).textContent = `${label}: ${on ? "ON" : "OFF"}`;
    $(id).setAttribute("aria-pressed", on);
  };
  $(id).addEventListener("click", () => {
    on = !on;
    settings.save(key, on ? "on" : "off");
    show();
    onChange(on);
  });
  show();
  return () => on;
}

// Wake word OFF (default): hands-free acts on everything you say.
// Wake word ON: only on "coach ..." / "hey coach ...", plus the follow-up window.
const wakeWordOn = toggle("wake-word", "Wake word", "wakeWord", false, updateStatus);

// Voice OFF: replies are shown as text only, never spoken.
const voiceOn = toggle("voice-on", "Voice", "voice", true, (on) => {
  if (on) return;
  if (window.speechSynthesis) speechSynthesis.cancel(); // stop mid-reply
  speaking = null;    // don't wait for the cancelled reply to report back
  startListening();   // so the mic comes straight back on
  updateStatus();
});

// Follow-up window: when the coach asks a question ("How many reps did you
// get?"), people just answer ("eight") without saying "coach" first. So for
// 8 seconds after a question (once it has been spoken, or as soon as it is
// shown when the voice is off), we accept an answer without the wake word.
const FOLLOW_UP_MS = 8000;
let followUpUntil = 0; // time (ms) the window closes; 0 = closed
let followUpTimer = null;
const answerWindowOpen = () => Date.now() < followUpUntil;

function openFollowUp() {
  followUpUntil = Date.now() + FOLLOW_UP_MS;
  console.log(`[follow-up] opened at ${Date.now()}, should expire at ${followUpUntil}`);
  clearTimeout(followUpTimer);
  followUpTimer = setTimeout(() => closeFollowUp("expired"), FOLLOW_UP_MS);
  updateStatus();
}

function closeFollowUp(why) {
  clearTimeout(followUpTimer);
  if (followUpUntil) console.log(`[follow-up] closed at ${Date.now()} (${why})`);
  followUpUntil = 0;
  updateStatus(); // label goes back to "Listening..."
}

// Send text to the server and show/speak the coach's answer.
// fromHandsFree: true when it came from the always-on microphone.
async function sendText(text, fromHandsFree = false) {
  if (!text.trim()) return;
  $("heard").textContent = text;
  const response = await fetch("/api/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await response.json();
  // Without a wake word, background talk reaches the coach. If it didn't
  // understand it, assume it wasn't meant for it: no reply, shown or spoken.
  if (fromHandsFree && !wakeWordOn() && data.heard.intent === "unknown") {
    $("heard").textContent = "Ignored: " + text;
    return;
  }
  cancelRest();                                  // any real turn stops the timer
  if (data.rest_seconds > 0) startRest(data.rest_seconds);
  $("source").textContent = data.heard.source === "ai" ? "AI (Groq)" : "Regex rules";
  $("reply").textContent = data.reply;
  showState(data);
  speak(data.reply);
}

// ---------- Rest timer ----------
// Counts down after a logged set. The coach speaks at 10 seconds left and at
// 0, through speak(), so the mic still pauses while it talks.
let restTimer = null;
let currentText = "";   // the coach's last description of the current set

function startRest(seconds) {
  let left = seconds;
  showRest(left);
  restTimer = setInterval(() => {
    left -= 1;
    if (left === 10) speak("Ten seconds.");
    if (left > 0) return showRest(left);
    stopRest();
    const message = "Time's up, go again. " + currentText;
    $("rest-done").textContent = message;            // announced once (aria-live)
    $("rest-done").classList.toggle("alert", !voiceOn()); // highlight if not spoken
    speak(message);
  }, 1000);
}

function showRest(left) {
  const seconds = String(left % 60).padStart(2, "0");
  $("rest").textContent = `Rest: ${Math.floor(left / 60)}:${seconds}`;
  $("rest").hidden = false;
}

function stopRest() {
  clearInterval(restTimer);
  restTimer = null;
  $("rest").hidden = true;
}

// Stop the countdown and clear any "Time's up" message.
function cancelRest() {
  stopRest();
  $("rest-done").textContent = "";
  $("rest-done").classList.remove("alert");
}

function showState(data) {
  currentText = data.current;
  // The coach describes the set as one sentence ("Bench Press, set 1 of 3:
  // 40 kilos for 10 reps."). Show its parts as separate figures; any other
  // sentence ("No routine yet.", "That's the workout done...") is shown as it is.
  const set = data.current.match(/^(.+), set (\d+) of (\d+): ([\d.]+) kilos for (\d+) reps\.$/);
  $("current").textContent = set ? set[1] : data.current;
  $("figures").hidden = !set;
  if (set) {
    $("set-figure").textContent = `Set ${set[2]} of ${set[3]}`;
    $("load-figure").textContent = `${set[4]} kg × ${set[5]} reps`;
  }
  renderLog(data.log);
  // The week appears once a routine is loaded; until then, a hint to set one up.
  const loaded = Boolean(data.week);
  $("week").hidden = $("today").hidden = !loaded;
  if (loaded) {
    renderWeek(data.week, data.today);
    $("today-name").textContent = data.today;
  }
  $("hint").textContent = loaded ? "Coach, what's first?"
    : "Coach, what workout should I do?";
}

// The week as chips; today's chip is marked for screen readers too.
function renderWeek(days, today) {
  const todayIndex = days.indexOf(today);   // today is day 1, the first match
  $("week-days").replaceChildren(...days.map((name, i) => {
    const chip = document.createElement("li");
    chip.textContent = name;
    if (i === todayIndex) {
      chip.className = "today";
      chip.setAttribute("aria-current", "true");
    }
    return chip;
  }));
}

// The coach must never hear itself: stop listening while it talks,
// and start again once it has finished.
function speak(text) {
  closeFollowUp("new reply"); // a new reply replaces any earlier question
  const isQuestion = text.trim().endsWith("?");
  if (!voiceOn()) {           // text only: nothing to wait for, mic stays on
    if (isQuestion) openFollowUp();
    return;
  }
  speechSynthesis.cancel(); // stop any reply that is still being read out
  const utterance = new SpeechSynthesisUtterance(text);
  const voice = chosenVoice();
  utterance.voice = voice;
  utterance.lang = voice ? voice.lang : "en-GB";
  speaking = utterance;
  if (handsFreeOn) handsFree.abort();
  utterance.onend = utterance.onerror = () => {
    if (speaking !== utterance) return; // an older reply we cancelled: ignore
    speaking = null;
    if (isQuestion) openFollowUp();     // the window starts once it has finished asking
    startListening();
    updateStatus();
  };
  updateStatus();
  speechSynthesis.speak(utterance);
}

// The coach's voice. Voices load asynchronously, so we fill the list now and
// again whenever the browser says the list has changed.
let englishVoices = [];

// The most natural-sounding English voice available, or null for the default.
function bestVoice(voices) {
  const natural = (v) => /natural|online/i.test(v.name);
  const british = (v) => v.lang.replace("_", "-") === "en-GB";
  return voices.find((v) => british(v) && natural(v))
    || voices.find(natural)
    || voices.find((v) => /^Google UK English (Female|Male)$/.test(v.name))
    || voices.find(british)
    || null;
}

function loadVoices() {
  englishVoices = speechSynthesis.getVoices().filter((v) => /^en[-_]/i.test(v.lang));
  $("voice").replaceChildren(
    new Option("Browser default", ""),
    ...englishVoices.map((v) => new Option(`${v.name} (${v.lang})`, v.name)),
  );
  // Use the saved choice if it still exists, otherwise the best one.
  const saved = settings.load("voiceName", null);
  const savedExists = saved === "" || englishVoices.some((v) => v.name === saved);
  $("voice").value = savedExists ? saved : (bestVoice(englishVoices)?.name ?? "");
  console.log(`[voice] ${englishVoices.length} English voices, using: ${$("voice").value || "browser default"}`);
}

const chosenVoice = () => englishVoices.find((v) => v.name === $("voice").value) || null;

if (window.speechSynthesis) {
  loadVoices();
  speechSynthesis.addEventListener("voiceschanged", loadVoices);
  $("voice").addEventListener("change", () => settings.save("voiceName", $("voice").value));
}

function updateStatus() {
  // data-state lets the CSS show the matching icon next to the words.
  $("status").dataset.state = speaking ? "speaking" : handsFreeOn ? "listening" : "off";
  $("status").textContent = speaking ? "Coach speaking..."
    : !handsFreeOn ? "Hands-free off"
    : answerWindowOpen() ? "Listening for your answer..." : "Listening...";
}

// (Re)start hands-free listening, unless it's switched off or the coach is talking.
function startListening() {
  if (!handsFreeOn || speaking) return;
  try { handsFree.start(); } catch (e) { /* already running: fine */ }
}

// Fixed log columns: [heading, key in each coach.py log entry].
const LOG_COLUMNS = [
  ["Exercise", "exercise"],
  ["Set", "set"],
  ["Weight (kg)", "weight"],
  ["Reps", "reps"],
  ["Note", "note"],
];

function renderLog(log) {
  const table = $("log");
  table.replaceChildren();
  if (!log || log.length === 0) return;
  const header = table.insertRow();
  LOG_COLUMNS.forEach(([heading]) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = heading;
    header.appendChild(th);
  });
  log.forEach((entry) => {
    const row = table.insertRow();
    LOG_COLUMNS.forEach(([, key]) => {
      row.insertCell().textContent = entry[key] ?? ""; // missing -> empty cell
    });
  });
}

// Voice input: one phrase per tap, final results only.
if (Recognition) {
  const recognition = new Recognition();
  recognition.lang = "en-GB";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (event) => sendText(event.results[0][0].transcript);
  recognition.onerror = (event) => { $("reply").textContent = "Didn't catch that (" + event.error + ")."; };
  recognition.onend = () => { $("talk").textContent = "Tap to talk"; };

  $("talk").addEventListener("click", () => {
    if (voiceOn()) speechSynthesis.cancel(); // don't let the coach's voice be picked up
    $("talk").textContent = "Listening...";
    recognition.start();
  });

  // Hands-free: listen all the time. With the wake word ON, only act on
  // "coach ..." / "hey coach ..." (or an answer inside the follow-up window).
  handsFree = new Recognition();
  handsFree.lang = "en-GB";
  handsFree.continuous = true;
  handsFree.interimResults = false;

  handsFree.onresult = (event) => {
    const text = event.results[event.resultIndex][0].transcript.trim();
    const match = text.match(/^(hey\s+)?coach\b[,.!]?\s*(.*)$/i);
    const command = (match ? match[2] : text).trim(); // without the wake word
    console.log(`[hands-free] final result at ${Date.now()}: "${text}" (window expires ${followUpUntil})`);
    if (!command) {                          // silence, or just "coach": nothing to send
      console.log("[hands-free] ignored: empty");
      return;
    }
    if (wakeWordOn() && !match && !answerWindowOpen()) {
      console.log("[hands-free] ignored: no wake word, window closed");
      $("heard").textContent = "Ignored (no wake word): " + text;
      return;
    }
    console.log(`[hands-free] accepted: ${match ? "wake word"
      : wakeWordOn() ? "inside follow-up window" : "wake word off"}`);
    closeFollowUp("answered");               // one answer closes the window
    sendText(command, true);
  };

  // Chrome stops listening after a silence: start again straight away.
  handsFree.onend = startListening;

  // "no-speech" and "aborted" are normal; onend restarts. Anything else
  // (e.g. microphone blocked) switches hands-free off so it can't loop.
  handsFree.onerror = (event) => {
    if (event.error === "no-speech" || event.error === "aborted") return;
    setHandsFree(false);
    $("reply").textContent = "Hands-free stopped (" + event.error + ").";
  };

  // The toggle. Tap to talk is disabled meanwhile: both need the microphone.
  function setHandsFree(on) {
    handsFreeOn = on;
    $("hands-free").textContent = "Hands-free: " + (on ? "ON" : "OFF");
    $("hands-free").setAttribute("aria-pressed", on);
    $("talk").disabled = on;
    if (on) startListening(); else handsFree.abort();
    updateStatus();
  }

  $("hands-free").disabled = false;
  $("hands-free").addEventListener("click", () => setHandsFree(!handsFreeOn));
} else {
  $("talk").disabled = true;
  $("unsupported").hidden = false;
}

// Typed fallback.
$("text-form").addEventListener("submit", (event) => {
  event.preventDefault();
  sendText($("text").value);
  $("text").value = "";
});

// New session: clears the routine, so the coach asks for days a week again.
$("reset").addEventListener("click", async () => {
  const data = await (await fetch("/api/reset", { method: "POST" })).json();
  cancelRest();
  $("heard").textContent = "...";
  $("source").textContent = "...";
  $("reply").textContent = "...";
  showState(data);
});

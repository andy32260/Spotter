const $ = (id) => document.getElementById(id);
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

let handsFreeOn = false;
let handsFree = null;  // the always-listening recogniser (set up below)
let speaking = null;   // the reply currently being read out, if any

// Follow-up window: when the coach asks a question ("How many reps did you
// get?"), people just answer ("eight") without saying "coach" first. So for
// 8 seconds after a question finishes, we accept an answer without the wake word.
const FOLLOW_UP_MS = 8000;
let followUpUntil = 0; // time (ms) the window closes; 0 = closed
let followUpTimer = null;
const answerWindowOpen = () => Date.now() < followUpUntil;

function closeFollowUp(why) {
  clearTimeout(followUpTimer);
  if (followUpUntil) console.log(`[follow-up] closed at ${Date.now()} (${why})`);
  followUpUntil = 0;
  updateStatus(); // label goes back to "Listening..."
}

// Send text to the server and show/speak the coach's answer.
async function sendText(text) {
  if (!text.trim()) return;
  $("heard").textContent = text;
  const response = await fetch("/api/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await response.json();
  $("source").textContent = data.heard.source === "ai" ? "AI (Groq)" : "Regex rules";
  $("reply").textContent = data.reply;
  showState(data);
  speak(data.reply);
}

function showState(data) {
  $("current").textContent = data.current;
  renderLog(data.log);
}

// The coach must never hear itself: stop listening while it talks,
// and start again once it has finished.
function speak(text) {
  speechSynthesis.cancel(); // stop any reply that is still being read out
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-GB";
  speaking = utterance;
  closeFollowUp("new reply"); // a new reply replaces any earlier question
  if (handsFreeOn) handsFree.abort();
  utterance.onend = utterance.onerror = () => {
    if (speaking !== utterance) return; // an older reply we cancelled: ignore
    speaking = null;
    if (text.trim().endsWith("?")) {   // the window starts once it has finished asking
      followUpUntil = Date.now() + FOLLOW_UP_MS;
      console.log(`[follow-up] opened at ${Date.now()}, should expire at ${followUpUntil}`);
      clearTimeout(followUpTimer);
      followUpTimer = setTimeout(() => closeFollowUp("expired"), FOLLOW_UP_MS);
    }
    startListening();
    updateStatus();
  };
  speechSynthesis.speak(utterance);
}

function updateStatus() {
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
    speechSynthesis.cancel(); // don't let the coach's voice be picked up
    $("talk").textContent = "Listening...";
    recognition.start();
  });

  // Hands-free: listen all the time, but only act on "coach ..." / "hey coach ...".
  handsFree = new Recognition();
  handsFree.lang = "en-GB";
  handsFree.continuous = true;
  handsFree.interimResults = false;

  handsFree.onresult = (event) => {
    const text = event.results[event.resultIndex][0].transcript.trim();
    const match = text.match(/^(hey\s+)?coach\b[,.!]?\s*(.*)$/i);
    console.log(`[hands-free] final result at ${Date.now()}: "${text}" (window expires ${followUpUntil})`);
    if (!match && !answerWindowOpen()) {
      console.log("[hands-free] ignored: no wake word, window closed");
      $("heard").textContent = "Ignored (no wake word): " + text;
      return;
    }
    console.log(`[hands-free] accepted: ${match ? "wake word" : "inside follow-up window"}`);
    const command = match ? match[2] : text; // strip the wake word if there is one
    if (!command) return;                    // just "coach": wait for the rest
    closeFollowUp("answered");               // one answer closes the window
    sendText(command);
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

$("reset").addEventListener("click", async () => {
  const data = await (await fetch("/api/reset", { method: "POST" })).json();
  $("heard").textContent = "...";
  $("source").textContent = "...";
  $("reply").textContent = "...";
  showState(data);
});

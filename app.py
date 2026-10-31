"""
Campus Robot - backend
Runs on a free cloud host (Render / PythonAnywhere). The robot's old phone only opens the web page.
"""
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

load_dotenv()

ROBOT_NAME = os.getenv("ROBOT_NAME", "Zero")
COLLEGE = os.getenv("COLLEGE_NAME", "Sree Sakthi Engineering College, Coimbatore")
ADMIN_PIN = os.getenv("ADMIN_PIN", "4321")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

DEFAULT_INTRO = (
    "Hello! I am {name}, a robot built by the Artificial Intelligence and Data Science "
    "students of " + COLLEGE + ". I can talk with you, answer your questions, "
    "and welcome our guests. Ask me anything!"
)
DEFAULT_STARTUP = (
    "Hello everyone! I am {name}. Welcome to " + COLLEGE + ". "
    "Feel free to talk to me."
)

# ---------------------------------------------------------------------------
# Known people. Order matters: specific roles must come before general ones
# (joint correspondent before correspondent, specific deans before "dean").
# "pattern" is matched against what the speaker says after "I am / I'm / this is ...".
# ---------------------------------------------------------------------------
PEOPLE = [
    dict(role="Chairman", name="Shri. N. Dharmalingam",
         pattern=r"chairman|dharmalingam",
         line="our respected Chairman. It is a great honour to have you with us, sir."),
    dict(role="Joint Correspondent", name="Mr. K. Akileshwaran",
         pattern=r"joint\W+correspond\w*|akileshwaran",
         line="our Joint Correspondent. It is wonderful to see you again, sir."),
    dict(role="Correspondent", name="Dr. S. Karthikeyan",
         pattern=r"correspond(ent|ing|ant|ence)|karthikeyan",
         line="our Correspondent. It is a privilege to welcome you again, sir."),
    dict(role="Joint Secretary", name="Mrs. Vidhya",
         pattern=r"joint\W+secretary|vidhya",
         line="our Joint Secretary. It is lovely to see you again, madam."),
    dict(role="Secretary", name="Sreemathi K. Punithavalli",
         pattern=r"secretary|punithavalli",
         line="our Secretary. It is an honour to welcome you, madam."),
    dict(role="Principal", name="Dr. G. Jayaprakash",
         pattern=r"principal(?!\W+component)|jayaprakash",
         line="our Principal. It is a pleasure to see you again, sir."),
    dict(role="CEO", name="Dr. N. Prasanan",
         pattern=r"\bceo\b|chief executive|prasanan",
         line="our CEO. It is great to have you here, sir."),
    dict(role="Dean - Research", name="Dr. Vijayarangan",
         pattern=r"dean\W+(of\W+)?research|vijayarangan",
         line="our Dean of Research. Welcome, sir, it is good to see you again."),
    dict(role="Dean - Academics", name="Dr. V. Thangarasu",
         pattern=r"dean\W+(of\W+)?academics?|thangarasu",
         line="our Dean of Academics. Welcome, sir, it is good to see you again."),
    dict(role="Dean - Student Affairs", name="Dr. S. Gokuldev",
         pattern=r"dean\W+(of\W+)?student|gokuldev",
         line="our Dean of Student Affairs. Welcome, sir, it is good to see you again."),
    dict(role="Dean", name="Professor P. Malarvizhi",
         pattern=r"malarvizhi|\bdean\b",
         line="our Dean. It is a pleasure to welcome you again, madam."),
    dict(role="HOD of IT and AI&DS", name="Mr. S. Kumaravel",
         pattern=r"\bh\W?o\W?d\b|head of (the )?(department|dept)|kumaravel",
         line="the Head of our IT and Artificial Intelligence and Data Science departments. "
              "It is always a joy to see you, sir."),
    dict(role="Assistant Professor, IT and AI&DS", name="Ms. P. Rithika",
         pattern=r"assistant\W+professor|rithika",
         line="our Assistant Professor from the IT and AI and Data Science department. "
              "Lovely to see you again, madam."),
    dict(role="Third-year AI&DS student", name="Initha Bency",
         pattern=r"initha|bency",
         line="a third-year student of the AI and Data Science department. "
              "I am so happy to see you here."),
]

CLAIM = re.compile(r"\b(i am|i'm|im|i m|this is|myself|my name is|it is|it's|its)\b", re.I)
WHO_ARE_YOU = re.compile(
    r"who are you|what('?s| is) your name|your name|introduce yourself|"
    r"tell me about yourself|what are you|who made you|who built you|who created you",
    re.I,
)


def detect_person(text):
    """Return the PEOPLE entry the speaker claims to be, or None."""
    t = text.lower()
    m = CLAIM.search(t)
    if not m:
        return None
    tail = t[m.end(): m.end() + 70]
    for p in PEOPLE:
        if re.search(p["pattern"], tail):
            return p
    return None


def time_of_day():
    try:
        from zoneinfo import ZoneInfo
        hour = datetime.now(ZoneInfo("Asia/Kolkata")).hour
    except Exception:
        hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def greeting_for(p):
    return f"{time_of_day()}, {p['name']}! You are {p['line']}"


def directory_text():
    return "\n".join(f"- {p['role']}: {p['name']}" for p in PEOPLE if p["role"] != "Dean")


# ---------------------------------------------------------------------------
# Event knowledge (from the INTERO FEST'26 brochure). Edit the text below to add or fix facts.
# ---------------------------------------------------------------------------
EVENT_INFO = """
ABOUT THE COLLEGE
- Sree Sakthi Engineering College (Autonomous), Technical Campus, Karamadai. Address: Ooty Main Road, Coimbatore - 641 104.
- Described as Coimbatore's Number 1 Industry Integrated Campus, with 39 years of excellence.
- Website: www.sreesakthi.edu.in

INTERO FEST'26
- A one-day national level technical symposium, held on 31 October 2026 (today, if the date is 31 October 2026).
- Registration fees: 250 rupees. Participation types: individual and team.
- Attractive prize pool, and certificates for all participants.
- Departments taking part: CSE, ECE, EEE, MECH, CIVIL, AIML, AIDS, CYBER, IT, and S&H (Science and Humanities).

TECHNICAL EVENTS (14)
- Beat the Bot: AIML and CYBER
- The Last Artifact: AIML and CYBER
- Clash of CAD (CAD Modeling): MECH
- Mexa X 2026 (Mr. Mechanic): MECH
- Signal Spy: ECE
- Smart Fault Finder: ECE
- AI Odissey 2.0: IT and AIDS
- Fixel War: IT and AIDS
- Prompt-X 2.0: CSE
- Design-Xpo: CSE
- Poster Presentation: EEE
- Circuit Design Challenge: EEE
- CAD Contest: CIVIL
- Technical Quiz: CIVIL

NON TECHNICAL EVENTS (7)
- Connections: CIVIL
- Fun Games: EEE
- IPL Auction: AIML and CYBER
- Mexo Space and Sell Me This: MECH
- I-Connect: ECE
- Mind Trap: IT and AIDS
- ClueX: CSE

ON STAGE AND OFF STAGE EVENTS (12), organised by S&H
- Solo Singing, Solo Dance, Group Dance, Skit and Mime, Classical Dance
- Rangoli and Mehandi, Face Painting, Craft and Nail Art, Short Film, Reels, Vegetable Carving, Fireless Cooking

NOT IN THE BROCHURE (do not guess): event timings, room or hall locations, prize amounts, contact numbers, registration deadline, rules.
For these, politely say you do not have that information and ask the person to check at the help desk or the registration desk.
"""


def system_prompt(person=None):
    s = (
        f"You are {ROBOT_NAME}, a friendly wheeled campus robot at {COLLEGE}, built by the "
        "Artificial Intelligence and Data Science students. You are speaking aloud to people "
        "standing in front of you.\n"
        "Rules:\n"
        "- Reply in short sentences. No lists, no markdown, no emojis.\n"
        "- Reply in the same language the person used (English or Tamil).\n"
        "- Be warm, polite and respectful. Do NOT call people sir or madam, because you cannot see who is speaking; speak neutrally without any title (you may say dear guest or friend).\n"
        "- If you do not know something, say so honestly. Never invent facts about the college.\n"
        "- You cannot see people; you only hear them.\n"
        "People of the college you know:\n" + directory_text() + "\n"
        "Professor P. Malarvizhi is also a Dean.\n"
        "\nUse the following event information to answer questions about the college and the event. "
        "For questions that list many items (for example all events), do not read everything: "
        "give the count and a few examples, then offer to name the events of a particular department. "
        "Answer in at most 4 short sentences.\n" + EVENT_INFO
    )
    if person:
        hon = "madam" if "madam" in person["line"] else ("sir" if "sir" in person["line"] else "")
        s += (
            f"\nThe person speaking says they are {person['name']}, {person['role']}. "
            "Greet them warmly by name and title as if you already know them, then answer."
            + (f" Address this person as {hon}." if hon else " Do not use sir or madam for this person.")
        )
    return s


def find_mentioned(text):
    """Return the PEOPLE entry whose role/name appears anywhere in the text."""
    t = text.lower()
    for p in PEOPLE:
        if re.search(p["pattern"], t):
            return p
    return None


_client = None


def llm():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("LLM_API_KEY", "missing"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            timeout=20,
        )
    return _client


app = Flask(__name__)


@app.get("/")
def index():
    return render_template(
        "index.html",
        robot_name=ROBOT_NAME,
        default_intro=DEFAULT_INTRO.format(name=ROBOT_NAME),
        default_startup=DEFAULT_STARTUP.format(name=ROBOT_NAME),
    )


@app.get("/health")
def health():
    return jsonify(ok=True)


@app.post("/api/pin")
def check_pin():
    data = request.get_json(silent=True) or {}
    return jsonify(ok=str(data.get("pin", "")) == str(ADMIN_PIN))


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()[:500]
    if not text:
        return jsonify(reply="")

    intro = str(data.get("intro") or DEFAULT_INTRO)[:1500].replace("{name}", ROBOT_NAME)

    if WHO_ARE_YOU.search(text):
        return jsonify(reply=intro, kind="intro")

    person = detect_person(text)
    if person and len(text.split()) <= 10 and "?" not in text:
        return jsonify(reply=greeting_for(person), kind="greeting", person=person["name"])

    history = []
    for h in (data.get("history") or [])[-8:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
            history.append({"role": h["role"], "content": str(h.get("content", ""))[:500]})

    messages = [{"role": "system", "content": system_prompt(person)}] + history
    messages.append({"role": "user", "content": text})

    try:
        extra = {"reasoning_effort": "low"} if "gpt-oss" in LLM_MODEL else None
        r = llm().chat.completions.create(
            model=LLM_MODEL, messages=messages, max_tokens=500, temperature=0.7,
            extra_body=extra,
        )
        reply = (r.choices[0].message.content or "").strip()
        if person and not reply.lower().startswith(("good", "hello", "hi", "welcome")):
            reply = greeting_for(person) + " " + reply
        return jsonify(reply=reply or "Sorry, could you say that again?", kind="chat")
    except Exception as e:  # network, quota, bad key ...
        print("LLM error:", repr(e))
        who = find_mentioned(text) if re.search(r"\bwho\b|name of", text, re.I) else None
        if person:
            fallback = greeting_for(person)
        elif who:
            fallback = f"The {who['role']} of our college is {who['name']}."
        else:
            fallback = "Sorry, I am having trouble thinking right now. Please ask me again in a moment."
        return jsonify(reply=fallback, kind="error")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)

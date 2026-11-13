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

ROBOT_NAME = os.getenv("ROBOT_NAME", "Optimus")
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
         pattern=r"\brithika\b",
         line="our Assistant Professor from the IT and AI and Data Science department. "
              "Lovely to see you again, madam."),
    dict(role="Assistant Professor", name="Vinothini S",
         pattern=r"vin(o|oa)thini|vinodhini",
         line="one of our Assistant Professors. It is lovely to see you again."),
    dict(role="Assistant Professor", name="Rajesh Kumar MS",
         pattern=r"\brajesh\b",
         line="one of our Assistant Professors. It is lovely to see you again."),
    dict(role="Assistant Professor", name="Sanjivgandhi H",
         pattern=r"sanji(v|e)v?\W?gandhi|\bgandhi\b|\bsanji(v|e)v\b",
         line="one of our Assistant Professors. It is lovely to see you again."),
    dict(role="Assistant Professor", name="Thirumurugan K",
         pattern=r"th?irumurugan|\bmurugan\b",
         line="one of our Assistant Professors. It is lovely to see you again."),
    dict(role="Assistant Professor", name="Arivaarndhani I",
         pattern=r"arivaarndhani|arivarndhani|arivarnthani|arivaarnthani|arivu\w*",
         line="one of our Assistant Professors. It is lovely to see you again."),
    dict(role="Assistant Professor", name="Ansha K",
         pattern=r"\b(ansha|amsha|aansha)\b",
         line="one of our Assistant Professors. It is lovely to see you again."),
    dict(role="Assistant Professor", name="Khavya K",
         pattern=r"\b(khavya|kavya|kaavya)\b",
         line="one of our Assistant Professors. It is lovely to see you again."),
    dict(role="Lab Administrator", name="Swetha",
         pattern=r"\b(swetha|sweta|shwetha|swedha)\b|lab\W+admin\w*",
         line="our Lab Administrator. It is lovely to see you again."),
    dict(role="NBA Committee Chairperson", name="Prof. Prerna Gaur",
         pattern=r"prerna|\bgaur\b|n\W?b\W?a\W+(committee\W+)?chair\w*",
         line="the Chairperson of the NBA committee. Welcome to Sree Sakthi Engineering College. "
              "It is a great honour to have you with us, madam."),
    dict(role="NBA Committee Expert Member, CSE", name="Prof. Bala Subramaniya Raman",
         pattern=r"bala\W?subr\w*|balasub\w*|subramani\w*|\braman\b",
         line="an expert member of the NBA committee from the CSE department. "
              "Welcome to Sree Sakthi Engineering College. It is a great honour to have you with us, sir."),
    dict(role="NBA Committee Expert Member, CSE", name="Prof. Vishal Gupta",
         pattern=r"vishal|\bgupta\b",
         line="an expert member of the NBA committee from the CSE department. "
              "Welcome to Sree Sakthi Engineering College. It is a great honour to have you with us, sir."),
    dict(role="Third-year AI&DS student", name="Initha Bency",
         pattern=r"initha|bency",
         line="a third-year student of the AI and Data Science department. "
              "I am so happy to see you here."),
    dict(role="Assistant Professor", name="", generic=True,
         pattern=r"assistant\W+professor",
         line="our respected Assistant Professor."),
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
    if p.get("generic"):
        return f"{time_of_day()}! Welcome, respected {p['role']}. It is lovely to see you here."
    return f"{time_of_day()}, {p['name']}! You are {p['line']}"


def directory_text():
    return "\n".join(f"- {p['role']}: {p['name']}" for p in PEOPLE if p["role"] != "Dean" and not p.get("generic"))


# ---------------------------------------------------------------------------
# Event knowledge (from the INTERO FEST'26 brochure). Edit the text below to add or fix facts.
# ---------------------------------------------------------------------------
EVENT_INFO = """
ABOUT THE COLLEGE
- Sree Sakthi Engineering College (Autonomous), Technical Campus, Karamadai. Address: Ooty Main Road, Coimbatore - 641 104.
- The INTERO FEST brochure describes the campus as Coimbatore's Number 1 Industry Integrated Campus. The college itself was established in 2010; do not say the college is 39 years old.
- Website: www.sreesakthi.edu.in
- SSEC is the short form of Sree Sakthi Engineering College.
- Technitix is the association of the IT and AI&DS (Artificial Intelligence and Data Science) department.

INTERO FEST'26
- A one-day national level technical symposium, held on 31 October 2026 (today, if the date is 31 October 2026).
- Registration fees: 250 rupees. Participation types: individual and team.
- Attractive prize pool, and certificates for all participants.
- Departments taking part: CSE, ECE, EEE, MECH, CIVIL, AIML, AIDS, CYBER, IT, and S&H (Science and Humanities).

COLLEGE PROFILE (from the college website)
- Sree Sakthi Engineering College (Autonomous) was established in 2010 by Shri N. Dharmalingam, Chairman, and Dr. S. Karthikeyan, Correspondent, of the Sree Sakthi Charitable Trust.
- Aim: value-based, high-quality technical education for students from both urban and rural backgrounds.
- Location: Karamadai, about 25 kilometres from Coimbatore, on the Coimbatore to Ooty national highway, in the foothills of the Western Ghats. The campus is 13.5 acres.
- Approved by AICTE, New Delhi. Affiliated to Anna University, Chennai. It is an autonomous institution.
- NAAC: accredited with B++ grade.
- Contact: phone +91 92445 04444 and +91 92445 02222; email ceo@sreesakthi.edu.in. Instagram: ssec_karamadai_official.
- Vision: to emerge as a centre of excellence in engineering education, research, innovation and entrepreneurship by fostering industry collaboration, practical skills and ethical values, so that students can address global challenges with creativity, sustainability and social responsibility.
- Mission: (1) nurture competent professionals and future leaders through learner-centric, innovative teaching and experiential learning; (2) cultivate a scientific temperament to give sustainable solutions to real-world problems; (3) promote ethical values, social responsibility and inclusive development through holistic education; (4) build a dynamic research ecosystem with industry, academia and research institutions; (5) encourage entrepreneurship through incubation centres and start-up support.
- Board of Management: Shri N. Dharmalingam (Chairman), Dr. S. Karthikeyan (Correspondent), Smt K. Punithavalli (Secretary), Mr K. Akileshwaran (Joint Correspondent), Ms V. Vidhya (Joint Secretary), Shri S. Murugan (Trustee), Smt D. Savithri (Trustee).
- Facilities and culture: outcome-based education, well-equipped laboratories, advanced computing facilities, a digital library, hostel, transport, food court, fitness centre, sports, clubs and cells, ATM. Over 10 Centres of Excellence. Also a TN Startup PIC centre.
- Skill Development and Placement Cell: skill gap assessments, hands-on training, mock interviews and company-specific coaching.
- Website figures: over 2400 students enrolled, over 10000 students graduated.

PROGRAMMES AND INTAKE FOR 2026-27
- Undergraduate, 4 years: Civil Engineering 30 (started 2010); Computer Science and Engineering 120 (2010); CSE with Artificial Intelligence and Machine Learning 60 (2023); CSE with Cyber Security 90 (2023); Electrical and Electronics Engineering 60 (2010); Electronics and Communication Engineering 120 (2010); Mechanical Engineering 60 (2010); B.Tech Artificial Intelligence and Data Science 120 (2024); B.Tech Information Technology 90 (2023); Mechatronics Engineering 60 (new in 2026).
- Postgraduate, 2 years: M.E. VLSI Design, intake 6 (started 2012); M.E. Computer Science and Engineering, intake 18 (started 2025).
- Doctoral research programmes are also offered.

NBA (NATIONAL BOARD OF ACCREDITATION)
- NBA was established in 1994 to evaluate the quality of programmes in technical institutions.
- SSEC has submitted Self-Assessment Reports for NBA accreditation of its undergraduate programmes in ECE, EEE, Mechanical Engineering and Civil Engineering.
- Do not claim that any programme is already NBA accredited. If asked about the result or status, say the programmes are under NBA evaluation and the outcome is decided by the NBA team.
- If asked about the NBA visit today, welcome the visiting team warmly and say the college is proud to share its work with them.

TECHNICAL EVENTS (14)
- Beat the Bot: AIML and CYBER
- The Last Artifact: AIML and CYBER
- Clash of CAD (CAD Modeling): MECH
- Mexa X 2026 (Mr. Mechanic): MECH
- Signal Spy: ECE
- Smart Fault Finder: ECE
- AI Odissey 2.0: IT and AIDS. Venue: CC5, IT and AI&DS department
- Fixel War: IT and AIDS. Venue: CC5, IT and AI&DS department
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
- Mind Trap: IT and AIDS. Venue: CC5, IT and AI&DS department
- ClueX: CSE

ON STAGE AND OFF STAGE EVENTS (12), organised by S&H
- Solo Singing, Solo Dance, Group Dance, Skit and Mime, Classical Dance
- Rangoli and Mehandi, Face Painting, Craft and Nail Art, Short Film, Reels, Vegetable Carving, Fireless Cooking

VENUES
- AI Odissey 2.0, Fixel War and Mind Trap are all held at CC5 in the IT and AI&DS department.

ABOUT THE COLLEGE (from the official website)
- Sree Sakthi Engineering College (SSEC), Autonomous, was established in 2010 by Shri. N. Dharmalingam, Chairman, and Dr. S. Karthikeyan, Correspondent, of the Sree Sakthi Charitable Trust, to give value-based, high-quality technical education to students from both urban and rural backgrounds.
- Location: Karamadai, about 25 kilometres from Coimbatore on the Coimbatore-Ooty national highway, in the foothills of the Western Ghats. The campus is 13.5 acres, with modern, eco-friendly buildings.
- Programmes:  9 undergraduate engineering programmes, 2 postgraduate programmes (M.E. VLSI Design and M.E. CSE), and doctoral research. All are affiliated to Anna University and approved by AICTE, New Delhi. The college is accredited by NAAC.
- Undergraduate departments: Mechanical, Civil, ECE, EEE, CSE, IT, AI and Data Science (AI&DS), AI and Machine Learning (AIML), and Cyber Security. There is also the Science and Humanities department.
- Numbers shown on the website: over 2400 students enrolled, over 10000 students graduated, over 10 Centres of Excellence.
- The college follows outcome-based education, with qualified faculty, well-equipped laboratories, advanced computing facilities and a digital library. Students take part in research, technical events, project exhibitions and industry collaborations. There is also a strong programme of sports and cultural activities.
- The Skill Development and Placement Cell runs skill gap assessments, hands-on training, mock interviews and company-specific coaching to prepare students for recruiters.
- Campus facilities listed on the website include library, food court, hostel, transport, clubs and cells, fitness centre, sports and an ATM. There is also a TN Startup PIC Centre and a Centre of Excellence section.
- Board of Management: Chairman Shri. N. Dharmalingam; Correspondent Dr. S. Karthikeyan; Secretary Smt. K. Punithavalli; Trustees Shri. S. Murugan and Smt. D. Savithri; Joint Correspondent Mr. K. Akileshwaran; Joint Secretary Ms. V. Vidhya.
- Vision: to emerge as a center of excellence in engineering education, research, innovation and entrepreneurship, by fostering industry collaboration, practical skills and ethical values, so that students can address global challenges with creativity, sustainability and social responsibility.
- Mission: (1) nurture competent professionals and future leaders through learner-centric, innovative teaching and experiential learning; (2) build a scientific temperament that gives sustainable solutions to real-world problems; (3) promote ethical values, social responsibility and inclusive development; (4) build a research ecosystem with industry, academia and research institutions; (5) encourage entrepreneurship through incubation centers and start-up support.
- Contact: phone +91 92445 04444 and +91 92445 02222, email ceo@sreesakthi.edu.in, website www.sreesakthi.edu.in. Address: Ooty Main Road, Coimbatore 641 104, Tamil Nadu.
- Recent college events: Sakthi Hackfest 2K26, SSEC World Record Attempt 2026, SSEC Sangamam 2K26, Sree Sakthi Vidhya Bhushan and Vidhya Shri Awards 2026, Chairman's 79th birthday celebration, department association inaugurations (including the IT and AI&DS association, Technitix).

NBA (NATIONAL BOARD OF ACCREDITATION)
- NBA was established in 1994 to evaluate and ensure the quality of programmes offered by technical institutions across India.
- According to the college website, SSEC has submitted Self-Assessment Reports (SAR) for accreditation of its undergraduate programmes in ECE, EEE, Mechanical Engineering and Civil Engineering, and follows outcome-based education aligned to NBA standards.
- The NBA committee is visiting the college today. Chairperson: Prof. Ms. Prerna Gaur. Expert members from the CSE department: Prof. Mr. Bala Subramaniya Raman and Prof. Mr. Vishal Gupta. Welcome them warmly and respectfully.

NOT IN THE BROCHURE (do not guess): event timings, venues of the other events, the NBA visit schedule, placement statistics, department-wise intake, faculty numbers, fee amounts, prize amounts, contact numbers, registration deadline, rules.
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
        "Answer in at most 4 short sentences. If a fact is not in the information below, say you do not have it and suggest asking the faculty coordinator; never guess numbers, rankings, placements or accreditation status.\n" + EVENT_INFO
    )
    if person:
        hon = "madam" if "madam" in person["line"] else ("sir" if "sir" in person["line"] else "")
        s += (
            f"\nThe person speaking says they are {person['name'] or 'an'} {person['role']}. "
            "Greet them warmly by name and title as if you already know them, then answer."
            + (f" Address this person as {hon}." if hon else " Do not use sir or madam for this person.")
        )
    return s


def find_mentioned(text):
    """Return the PEOPLE entry whose role/name appears anywhere in the text."""
    t = text.lower()
    for p in PEOPLE:
        if not p.get("generic") and re.search(p["pattern"], t):
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

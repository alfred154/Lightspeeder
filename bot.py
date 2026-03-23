import os
import random
import discord
from discord.ext import commands
import math
import aiohttp
import re
from difflib import SequenceMatcher

# ============================================================
#  GLOBALS
# ============================================================

# Each entry: {"title": str, "body": str, "source": "employee" or "manager"}
HANDBOOK_SECTIONS = []
USER_SESSIONS = {}  # per-user troubleshooting sessions

HARDWARE_KEYWORDS = {
    "printer": ["printer", "receipt printer", "print", "printing", "printer offline", "printer not working"],
    "scanner": ["scanner", "barcode", "scan", "barcode scanner", "scanner not working"],
    "drawer": ["drawer", "cash drawer", "drawer stuck", "drawer not opening"],
    "dejavoo": ["dejavoo", "terminal", "card reader", "pin pad"]
}

ESCALATION_CONTACTS = """
If the issue is still not resolved, contact support:

Savannah (Day Support): 409‑599‑8916
Calvin (Night Support): 346‑702‑2489
Daemon (Head of Retail Systems): 409‑363‑9306
Alfred (Retail Systems Specialist): 832‑276‑8415
Patricia (Retail Systems Specialist): 346‑304‑0648
"""

MANAGER_KEYWORDS = [
    "manager",
    "override",
    "approval",
    "discount",
    "void",
    "end of day",
    "closeout",
    "close out",
    "manager refund",
    "manager login",
    "manager mode",
    "manager permissions",
    "manager override"
]

# ============================================================
#  HANDBOOK LOADING & SECTION PARSING
# ============================================================

def is_header(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if line[0].isdigit():
        return False
    if line.startswith("-") or line.startswith("*"):
        return False
    if "http" in line:
        return False
    if "@" in line:
        return False
    if len(line) > 100:
        return False
    if "." in line:
        return False

    words = line.split()
    if len(words) < 2:
        return False

    capitalized_words = sum(1 for w in words if w[0].isupper())
    return capitalized_words >= len(words) * 0.6

def load_file_sections(filename: str, source: str):
    if not os.path.exists(filename):
        print(f"Handbook file not found: {filename}")
        return []

    with open(filename, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    sections = []
    current_title = None
    current_lines = []

    for line in lines:
        if is_header(line):
            if current_title and current_lines:
                sections.append({
                    "title": current_title.strip(),
                    "body": "\n".join(current_lines).strip(),
                    "source": source
                })
            current_title = line.strip()
            current_lines = []
        else:
            if current_title:
                current_lines.append(line)

    if current_title and current_lines:
        sections.append({
            "title": current_title.strip(),
            "body": "\n".join(current_lines).strip(),
            "source": source
        })

    print(f"Loaded {len(sections)} sections from {filename} ({source}).")
    return sections

def load_handbook():
    global HANDBOOK_SECTIONS
    HANDBOOK_SECTIONS = []

    # Employee handbook
    HANDBOOK_SECTIONS.extend(load_file_sections("Lightspeed_Handbook.txt", "employee"))

    # Manager handbook
    HANDBOOK_SECTIONS.extend(load_file_sections("Manager_Lightspeed_Handbook.txt", "manager"))

    print(f"Total sections loaded: {len(HANDBOOK_SECTIONS)}")

# ============================================================
#  FUZZY MATCHING & SECTION SELECTION
# ============================================================

def fuzzy_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()

def score_section(query: str, title: str, body: str) -> float:
    q = query.lower()
    t = title.lower()
    b = body.lower()

    score = 0
    score += fuzzy_ratio(q, t) * 5

    for word in q.split():
        if word in t:
            score += 3
        if word in b:
            score += 1

    return score

def is_manager_query(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in MANAGER_KEYWORDS)

def find_best_sections(query: str):
    best_employee = None
    best_employee_score = 0
    best_manager = None
    best_manager_score = 0

    for entry in HANDBOOK_SECTIONS:
        title = entry["title"]
        body = entry["body"]
        source = entry["source"]

        s = score_section(query, title, body)
        if source == "employee":
            if s > best_employee_score:
                best_employee_score = s
                best_employee = entry
        else:
            if s > best_manager_score:
                best_manager_score = s
                best_manager = entry

    # If both are extremely low, treat as no match
    if best_employee_score < 0.2:
        best_employee = None
    if best_manager_score < 0.2:
        best_manager = None

    return best_employee, best_manager

def format_merged_answer(query: str, employee_entry, manager_entry):
    # Employee first, then Manager (Advanced)
    # Title preference: manager title if exists, else employee
    title = None
    if manager_entry:
        title = manager_entry["title"]
    elif employee_entry:
        title = employee_entry["title"]
    else:
        title = "Lightspeed Information"

    parts = [f"**{title}**\n"]

    if employee_entry:
        body = employee_entry["body"]
        if len(body) > 1500:
            body = body[:1500] + "\n\n...(truncated)..."
        parts.append("**Employee Instructions:**\n" + body + "\n")

    if manager_entry:
        body = manager_entry["body"]
        if len(body) > 1500:
            body = body[:1500] + "\n\n...(truncated)..."
        parts.append("---\n**Manager Instructions (Advanced):**\n" + body)

    return "\n".join(parts).strip()

def format_single_answer(entry):
    if not entry:
        return None
    title = entry["title"]
    body = entry["body"]
    if len(body) > 1500:
        body = body[:1500] + "\n\n...(truncated)..."
    return f"**{title}**\n\n{body}"

# ============================================================
#  HARDWARE DETECTION
# ============================================================

def detect_hardware_category(query: str):
    q = query.lower()
    for category, keywords in HARDWARE_KEYWORDS.items():
        for kw in keywords:
            if fuzzy_ratio(q, kw) > 0.6 or kw in q:
                return category
    return None

# ============================================================
#  STEP EXTRACTION
# ============================================================

def extract_steps(text: str):
    return re.findall(r"\d+\.\s.*", text)

def fallback_steps(category):
    if category == "printer":
        return [
            "Check if the printer has a solid green light.",
            "Ensure the Ethernet cable is firmly connected.",
            "Verify the iPad is on the correct WiFi.",
            "Open Lightspeed → Settings → Hardware → Search for printer.",
            "Power cycle the printer.",
            "Restart the iPad."
        ]
    if category == "scanner":
        return [
            "Ensure the scanner is charged.",
            "Restart the scanner.",
            "Check Bluetooth connection.",
            "Try scanning a known good barcode.",
            "Toggle keyboard mode on the scanner."
        ]
    if category == "drawer":
        return [
            "Ensure the printer is online (drawer depends on printer).",
            "Check the drawer cable connected to the printer.",
            "Perform a test print.",
            "Power cycle the drawer and printer."
        ]
    if category == "dejavoo":
        return [
            "Ensure the terminal is powered on.",
            "Check the network connection.",
            "Restart the terminal.",
            "Verify Lightspeed is paired with the terminal.",
            "Run a test transaction."
        ]
    return ["No steps available."]

# ============================================================
#  TROUBLESHOOTING SESSION MANAGEMENT
# ============================================================

def start_session(user_id, category, steps):
    USER_SESSIONS[user_id] = {"category": category, "steps": steps, "index": 0}

def get_session(user_id):
    return USER_SESSIONS.get(user_id)

def advance_session(user_id):
    session = USER_SESSIONS.get(user_id)
    if not session:
        return None

    session["index"] += 1
    if session["index"] >= len(session["steps"]):
        del USER_SESSIONS[user_id]
        return "done"

    return session["steps"][session["index"]]

def stop_session(user_id):
    USER_SESSIONS.pop(user_id, None)

# ============================================================
#  DISTANCE TOOL
# ============================================================

async def geocode_location(query: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1, "countrycodes": "us"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers={"User-Agent": "LightspeederBot"}) as resp:
            data = await resp.json()
            if not data:
                return None
            return float(data[0]["lat"]), float(data[0]["lon"])

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lat2 - lon1)
    a = (
        math.sin(dlat/2)**2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon/2)**2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

async def get_distance_between_locations(loc1, loc2):
    p1 = await geocode_location(loc1)
    p2 = await geocode_location(loc2)
    if not p1 or not p2:
        return None, None, None, None

    lat1, lon1 = p1
    lat2, lon2 = p2

    straight = haversine(lat1, lon1, lat2, lon2)
    drive_time_hours = straight / 45
    drive_minutes = int(drive_time_hours * 60)

    return straight, drive_minutes, p1, p2

# ============================================================
#  DISCORD BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ============================================================
#  HELP MENU
# ============================================================

HELP_TEXT = """
**Lightspeeder Help Menu**

**Ask any Lightspeed question:**
@bot how do I clock in
@bot how do I search products
@bot how do I log in

**Start hardware troubleshooting:**
@bot printer not working
@bot scanner not scanning
@bot cash drawer stuck
@bot dejavoo not connecting

**During troubleshooting:**
Say **next** to continue
Say **stop** to cancel

**Distance tool:**
@bot distance from Houston to Dallas

**Escalation Contacts:**
""" + ESCALATION_CONTACTS

# ============================================================
#  BOT EVENTS
# ============================================================

@bot.event
async def on_ready():
    print(f"Lightspeeder bot online as {bot.user}")
    load_handbook()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()
    user_id = message.author.id

    # HELP MENU
    if bot.user in message.mentions and "help" in content:
        await message.reply(HELP_TEXT)
        return

    # ACTIVE TROUBLESHOOTING SESSION (HYBRID MODE)
    session = get_session(user_id)
    if session:
        # Flow control
        if content.strip() == "next":
            next_step = advance_session(user_id)
            if next_step == "done":
                await message.reply("All steps completed.\n\n" + ESCALATION_CONTACTS)
            else:
                await message.reply(
                    f"**Step {session['index']+1}/{len(session['steps'])}:**\n{next_step}"
                )
            return

        if content.strip() == "stop":
            stop_session(user_id)
            await message.reply("Troubleshooting cancelled.")
            return

        # Prevent new hardware flow
        new_hw = detect_hardware_category(content)
        if new_hw:
            await message.reply(
                f"You're already troubleshooting the **{session['category']}**.\n"
                "Say **next** to continue or **stop** to cancel."
            )
            return

        # Question detection
        def is_question(text):
            return "?" in text or any(text.startswith(q) for q in ["how", "what", "why", "where", "when"])

        if is_question(content):
            emp, mgr = find_best_sections(content)
            if emp or mgr:
                answer = None
                if is_manager_query(content) and (emp or mgr):
                    answer = format_merged_answer(content, emp, mgr)
                else:
                    # Prefer employee if not explicitly manager-level
                    if emp:
                        answer = format_single_answer(emp)
                    elif mgr:
                        answer = format_single_answer(mgr)

                if answer:
                    await message.reply(
                        f"{answer}\n\nYou're still in **{session['category']} troubleshooting** — say **next** to continue."
                    )
                    return

            await message.reply(
                "I couldn't find anything in the handbook for that question.\n\n"
                f"You're still in **{session['category']} troubleshooting** — say **next** to continue."
            )
            return

        # Other messages → normal Q&A + reminder
        emp, mgr = find_best_sections(content)
        if emp or mgr:
            answer = None
            if is_manager_query(content) and (emp or mgr):
                answer = format_merged_answer(content, emp, mgr)
            else:
                if emp:
                    answer = format_single_answer(emp)
                elif mgr:
                    answer = format_single_answer(mgr)

            if answer:
                await message.reply(
                    f"{answer}\n\nYou're still in **{session['category']} troubleshooting** — say **next** to continue."
                )
                return

        await message.reply(
            f"You're still in **{session['category']} troubleshooting** — say **next** to continue or **stop** to cancel."
        )
        return

    # DISTANCE TOOL
    if bot.user in message.mentions and "distance" in content:
        try:
            cleaned = (
                message.content
                .replace(f'<@{bot.user.id}>', '')
                .replace(f'<@!{bot.user.id}>', '')
                .strip()
            )

            if " to " not in cleaned:
                await message.reply("Format: `@Bot distance from LOCATION1 to LOCATION2`")
                return

            loc1, loc2 = cleaned.split(" to ", 1)
            loc1 = loc1.replace("distance", "").replace("from", "").strip()
            loc2 = loc2.strip()

            await message.channel.typing()

            straight, drive_minutes, p1, p2 = await get_distance_between_locations(loc1, loc2)
            if straight is None:
                await message.reply("I couldn't find one of those locations.")
                return

            hours = drive_minutes // 60
            mins = drive_minutes % 60

            await message.reply(
                f"{loc1.title()} to {loc2.title()}\n"
                f"Distance: {straight:.1f} Miles\n"
                f"Drive Time: {hours}h {mins:02d}min"
            )
            return

        except Exception as e:
            await message.reply(f"Error calculating distance: {e}")
            return

    # NEW LIGHTSPEED QUESTION OR TROUBLESHOOTING
    if bot.user in message.mentions:
        query = (
            message.content
            .replace(f'<@{bot.user.id}>', '')
            .replace(f'<@!{bot.user.id}>', '')
            .strip()
        )

        # Detect hardware category
        category = detect_hardware_category(query)

        # Hardware → start troubleshooting
        if category:
            emp, mgr = find_best_sections(query)
            # For troubleshooting, prefer manager steps if available
            chosen_body = None
            if mgr:
                chosen_body = mgr["body"]
            elif emp:
                chosen_body = emp["body"]

            steps = extract_steps(chosen_body) if chosen_body else []
            if not steps:
                steps = fallback_steps(category)

            start_session(user_id, category, steps)

            await message.reply(
                f"**{category.title()} Troubleshooting — Step 1/{len(steps)}**\n{steps[0]}\n\n"
                "Say **next** when done or **stop** to cancel."
            )
            return

        # Normal Q&A
        emp, mgr = find_best_sections(query)
        if emp or mgr:
            if is_manager_query(query) and (emp or mgr):
                answer = format_merged_answer(query, emp, mgr)
            else:
                if emp:
                    answer = format_single_answer(emp)
                elif mgr:
                    answer = format_single_answer(mgr)
                else:
                    answer = None

            if answer:
                await message.reply(answer)
                return

        await message.reply("I couldn't find anything in the Lightspeed handbook for that question.")
        return

    await bot.process_commands(message)

# ============================================================
#  BASIC COMMANDS
# ============================================================

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def echo(ctx, *, message: str):
    await ctx.send(message)

@bot.command()
async def add(ctx, a: int, b: int):
    await ctx.send(f"{a + b}")

@bot.command()
async def info(ctx):
    await ctx.send(f"I'm online and running on Railway as {bot.user}!")

# ============================================================
#  FUN COMMANDS
# ============================================================

@bot.command()
async def eightball(ctx, *, question: str):
    responses = [
        "Yes.", "No.", "Absolutely.", "Definitely not.",
        "Ask again later.", "It’s unclear.", "Without a doubt.",
        "My sources say no.", "Probably.", "I don’t think so."
    ]
    await ctx.send(f"🎱 {random.choice(responses)}")

@bot.command()
async def coinflip(ctx):
    await ctx.send(f"🪙 {random.choice(['Heads', 'Tails'])}")

@bot.command()
async def roll(ctx, sides: int = 6):
    if sides < 2:
        await ctx.send("Dice must have at least 2 sides.")
        return
    result = random.randint(1, sides)
    await ctx.send(f"🎲 You rolled a **{result}** on a {sides}-sided die.")

@bot.command()
async def choose(ctx, *options):
    if len(options) < 2:
        await ctx.send("Give me at least two choices!")
        return
    await ctx.send(f"I choose: **{random.choice(options)}**")

# ============================================================
#  RUN BOT
# ============================================================

bot.run(os.getenv("DISCORD_TOKEN"))

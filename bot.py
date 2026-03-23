import os
import random
import discord
from discord.ext import commands
import math
import aiohttp

# -------------------------------
# LOAD & PARSE LIGHTSPEED HANDBOOK
# -------------------------------

HANDBOOK_SECTIONS = {}

def load_handbook():
    global HANDBOOK_SECTIONS
    filename = "Lightspeed_Handbook.txt"
    if not os.path.exists(filename):
        print("Handbook file not found:", filename)
        HANDBOOK_SECTIONS = {}
        return

    with open(filename, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    sections = {}
    current_title = None
    current_lines = []

    def is_header(line: str) -> bool:
        line = line.strip()
        if not line:
            return False
        if len(line) > 80:
            return False
        if any(line.startswith(ch) for ch in ("1.", "2.", "3.", "-", "*")):
            return False
        if "." in line:
            return False
        # treat as header if it has letters and spaces, no @ or :
        if any(c.isalpha() for c in line) and all(c.isalnum() or c.isspace() or c in "&/" for c in line):
            return True
        return False

    for line in lines:
        if is_header(line):
            # save previous section
            if current_title and current_lines:
                sections[current_title.lower()] = "\n".join(current_lines).strip()
            current_title = line.strip()
            current_lines = []
        else:
            if current_title:
                current_lines.append(line)

    if current_title and current_lines:
        sections[current_title.lower()] = "\n".join(current_lines).strip()

    HANDBOOK_SECTIONS = sections
    print(f"Loaded {len(HANDBOOK_SECTIONS)} handbook sections.")

def score_section(query: str, title: str, body: str) -> int:
    q_words = [w for w in query.lower().split() if len(w) > 2]
    text = (title + " " + body).lower()
    score = 0
    for w in q_words:
        if w in text:
            score += 2
        if w in title.lower():
            score += 3
    return score

def find_best_handbook_answer(query: str):
    if not HANDBOOK_SECTIONS:
        return None

    best_title = None
    best_body = None
    best_score = 0

    for title, body in HANDBOOK_SECTIONS.items():
        s = score_section(query, title, body)
        if s > best_score:
            best_score = s
            best_title = title
            best_body = body

    if best_score == 0 or not best_body:
        return None

    # trim long responses a bit
    if len(best_body) > 1200:
        best_body = best_body[:1200] + "\n\n...(truncated)..."

    return f"**{best_title.title()}**\n\n{best_body}"


# -------------------------------
# LOCATION / DISTANCE UTILITIES
# -------------------------------

async def geocode_location(query: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "us"
    }

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
        math.sin(dlat / 2) ** 2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def get_distance_between_locations(loc1: str, loc2: str):
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


# ---- Intents ----
intents = discord.Intents.default()
intents.message_content = True

# ---- Bot Setup ----
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Lightspeeder bot online as {bot.user}")
    load_handbook()


@bot.event
async def on_message(message):
    content_lower = message.content.lower()

    # DISTANCE QUERY
    if bot.user in message.mentions and "distance" in content_lower:
        try:
            cleaned = (
                message.content
                .replace(f'<@{bot.user.id}>', '')
                .replace(f'<@!{bot.user.id}>', '')
                .strip()
            )

            if " to " not in cleaned.lower():
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

    # LIGHTSPEED Q&A (any question from handbook)
    if bot.user in message.mentions and "distance" not in content_lower:
        query = (
            message.content
            .replace(f'<@{bot.user.id}>', '')
            .replace(f'<@!{bot.user.id}>', '')
            .strip()
        )

        answer = find_best_handbook_answer(query)
        if answer:
            await message.reply(answer)
            return
        else:
            await message.reply("I couldn't find anything in the Lightspeed handbook for that question.")
            return

    if message.author.bot:
        return

    if bot.user in message.mentions:
        await message.channel.send("You tagged me! Ask me any Lightspeed question or use `distance`.")

    await bot.process_commands(message)


# ---- Basic Commands ----

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


# ---- Fun Commands ----

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


bot.run(os.getenv("DISCORD_TOKEN"))

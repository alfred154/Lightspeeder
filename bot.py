import os
import random
import discord
from discord.ext import commands
import math
import aiohttp

# -------------------------------
# LOAD LIGHTSPEED HANDBOOK
# -------------------------------

HANDBOOK_TEXT = ""

if os.path.exists("Lightspeed Handbook.txt"):
    with open("Lightspeed Handbook.txt", "r", encoding="utf-8") as f:
        HANDBOOK_TEXT = f.read().lower()
else:
    HANDBOOK_TEXT = "handbook_missing"


def search_handbook(keywords):
    """Return the first matching section from the handbook."""
    if HANDBOOK_TEXT == "handbook_missing":
        return None

    for kw in keywords:
        if kw in HANDBOOK_TEXT:
            # Return ~500 characters around the keyword
            idx = HANDBOOK_TEXT.index(kw)
            start = max(0, idx - 200)
            end = min(len(HANDBOOK_TEXT), idx + 300)
            return HANDBOOK_TEXT[start:end].strip()

    return None


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
        async with session.get(url, params=params, headers={"User-Agent": "TesterBot"}) as resp:
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

# -------------------------------
# LIGHTSPEED HARDWARE TROUBLESHOOTING (A)
# -------------------------------

def lightspeed_hardware_response(msg):
    msg = msg.lower()

    # Search handbook first
    if "printer" in msg:
        section = search_handbook(["printer", "receipt printer", "printing"])
        if section:
            return "**Lightspeed Printer Troubleshooting (from Handbook)**\n" + section

    if "scanner" in msg or "barcode" in msg:
        section = search_handbook(["scanner", "barcode"])
        if section:
            return "**Lightspeed Scanner Troubleshooting (from Handbook)**\n" + section

    if "cash drawer" in msg:
        section = search_handbook(["cash drawer", "drawer"])
        if section:
            return "**Lightspeed Cash Drawer Troubleshooting (from Handbook)**\n" + section

    return None


# -------------------------------
# LIGHTSPEED TRAINING ANSWERS (E)
# -------------------------------

def lightspeed_training_response(msg):
    msg = msg.lower()

    if "refund" in msg:
        section = search_handbook(["refund", "return"])
        if section:
            return "**Refund Instructions (from Handbook)**\n" + section

    if "reprint" in msg or "receipt" in msg:
        section = search_handbook(["receipt", "reprint"])
        if section:
            return "**Receipt Instructions (from Handbook)**\n" + section

    if "void" in msg:
        section = search_handbook(["void"])
        if section:
            return "**Void Instructions (from Handbook)**\n" + section

    if "clock" in msg:
        section = search_handbook(["clock", "time clock"])
        if section:
            return "**Clock In/Out Instructions (from Handbook)**\n" + section

    return None


# ---- Events ----
@bot.event
async def on_ready():
    print(f"Tester bot online as {bot.user}")


@bot.event
async def on_message(message):

    content_lower = message.content.lower()

    # -----------------------------------------
    # DISTANCE QUERY
    # -----------------------------------------
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

    # -----------------------------------------
    # LIGHTSPEED HARDWARE TROUBLESHOOTING (A)
    # -----------------------------------------
    if bot.user in message.mentions:
        hardware = lightspeed_hardware_response(content_lower)
        if hardware:
            await message.reply(hardware)
            return

    # -----------------------------------------
    # LIGHTSPEED TRAINING ANSWERS (E)
    # -----------------------------------------
    if bot.user in message.mentions:
        training = lightspeed_training_response(content_lower)
        if training:
            await message.reply(training)
            return

    # Ignore other bots
    if message.author.bot:
        return

    # Generic mention response
    if bot.user in message.mentions:
        await message.channel.send("You tagged me! I'm alive on Railway.")

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


# ---- Start Bot ----
bot.run(os.getenv("DISCORD_TOKEN"))

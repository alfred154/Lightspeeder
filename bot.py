import os
import random
import discord
from discord.ext import commands
import math
import aiohttp

# -------------------------------
# LOCATION / DISTANCE UTILITIES
# -------------------------------

async def geocode_location(query: str):
    """Convert a location string into latitude/longitude using OpenStreetMap."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers={"User-Agent": "TesterBot"}) as resp:
            data = await resp.json()
            if not data:
                return None
            return float(data[0]["lat"]), float(data[0]["lon"])


def haversine(lat1, lon1, lat2, lon2):
    """Straight-line distance between two coordinates."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def get_distance_between_locations(loc1: str, loc2: str):
    """Geocode both locations and calculate distance."""
    p1 = await geocode_location(loc1)
    p2 = await geocode_location(loc2)

    if not p1 or not p2:
        return None, None, None, None

    lat1, lon1 = p1
    lat2, lon2 = p2

    straight = haversine(lat1, lon1, lat2, lon2)

    # Simple drive-time estimate (45 mph avg)
    drive_time_hours = straight / 45
    drive_minutes = int(drive_time_hours * 60)

    return straight, drive_minutes, p1, p2


# ---- Intents ----
intents = discord.Intents.default()
intents.message_content = True  # REQUIRED for reading messages

# ---- Bot Setup ----
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- Events ----
@bot.event
async def on_ready():
    print(f"Tester bot online as {bot.user}")


@bot.event
async def on_message(message):

    # -----------------------------------------
    # DISTANCE QUERY: "@bot distance X to Y"
    # -----------------------------------------
    content_lower = message.content.lower()

    if bot.user in message.mentions and "distance" in content_lower:
        try:
            cleaned = (
                message.content
                .replace(f'<@{bot.user.id}>', '')
                .replace(f'<@!{bot.user.id}>', '')
                .strip()
            )

            # MUST use " to " with spaces
            if " to " not in cleaned.lower():
                await message.reply("Format: `@Bot distance from LOCATION1 to LOCATION2`")
                return

            # Split on " to " ONLY
            loc1, loc2 = cleaned.lower().split(" to ", 1)

            # Clean up prefixes
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


    # Ignore other bots
    if message.author.bot:
        return

    # If the bot is tagged normally
    if bot.user in message.mentions:
        await message.channel.send("You tagged me! I'm alive on Railway.")

    # Allow commands to run
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

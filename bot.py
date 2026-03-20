import os
import discord
from discord.ext import commands

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
    if message.author.bot:
        return

    # If the bot is tagged in the message
    if bot.user in message.mentions:
        await message.channel.send("You tagged me! I'm alive on Railway.")

    # Allow commands to run
    await bot.process_commands(message)

# ---- Commands ----

# Simple ping command
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# Echo command
@bot.command()
async def echo(ctx, *, message: str):
    await ctx.send(message)

# Add two numbers
@bot.command()
async def add(ctx, a: int, b: int):
    await ctx.send(f"{a + b}")

# Bot info
@bot.command()
async def info(ctx):
    await ctx.send(f"I'm online and running on Railway as {bot.user}!")

# ---- Run Bot ----
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)

import os
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)

intents = discord.Intents.default()
intents.message_content = True  # REQUIRED for reading messages

bot = commands.Bot(command_prefix="!", intents=intents)

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

    await bot.process_commands(message)

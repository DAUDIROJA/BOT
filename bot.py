import discord
from discord.ext import commands
import os
import random

# Set up intents
intents = discord.Intents.default()
intents.message_content = True  # Allows bot to read message content

# Create bot with command prefix and intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Bot ready event
@bot.event
async def on_ready():
    print("BOT is ready and online!")

# Command: !hi
@bot.command()
async def hi(ctx):
    await ctx.send("Yo bro, BOT here for you!")

# Command: !status
@bot.command()
async def status(ctx):
    await ctx.send("Bot is running smoothly on Render ☁️💪")

# Command: !helpme
@bot.command()
async def helpme(ctx):
    help_text = (
        "**Available Commands:**\n"
        "`!hi` - Greets you.\n"
        "`!status` - Shows if the bot is running.\n"
        "`!helpme` - Lists available commands.\n"
        "`!joke` - Sends a random trading-style joke.\n"
    )
    await ctx.send(help_text)

# Command: !joke
@bot.command()
async def joke(ctx):
    jokes = [
        "Why did the trader go broke? Because he lost interest!",
        "I told my bot to trade smart. Now it only watches charts and does nothing. 😂",
        "Why do traders love the sun? Because it rises after every dip!",
        "My bot said it's bullish... then it bought coffee ☕️ instead of stocks."
    ]
    await ctx.send(random.choice(jokes))

# Run the bot using token from environment variables
bot.run(os.getenv("DISCORD_TOKEN"))

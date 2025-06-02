import discord
from discord.ext import commands
import os

# Set up intents
intents = discord.Intents.default()
intents.message_content = True  # Allows bot to see message content

# Create bot with intents
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("BOT is ready!")

@bot.command()
async def hi(ctx):
    await ctx.send("Yo bro, BOT here for you!")

# Use environment variable for token
bot.run(os.getenv("DISCORD_TOKEN"))

import discord
from discord.ext import commands
import os

# Set up intents
intents = discord.Intents.default()
intents.message_content = True  # Allows bot to see message content
intents.members = True         # Allows bot to see server members

# Create bot with intents
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("BOT is ready!")

@bot.command()
async def hello(ctx):
    await ctx.send("Yo bro, BOT here to help the fam!")

@bot.command()
async def price(ctx):
    await ctx.send("Bitcoin price: $12345 (fake for now!)")

bot.run(os.getenv("DISCORD_TOKEN"))

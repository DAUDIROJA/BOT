import discord
from discord.ext import commands
import os
import asyncio
import websockets
import json

# ─────── Discord Bot Setup ─────── #
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("✅ BOT is online and ready!")

@bot.command()
async def hi(ctx):
    await ctx.send("Yo bro, BOT here for you!")

@bot.command()
async def status(ctx):
    await ctx.send("Bot is up and ready to trade BTCUSDz on Deriv demo 🚀")

# ─────── Deriv Trading Logic ─────── #
async def place_btc_trade():
    url = "wss://ws.deriv.net/websockets/v3?app_id=1089"
    token = os.getenv("DERIV_TOKEN")  # Insert this in Render environment

    async with websockets.connect(url) as ws:
        # 1. Authorize
        await ws.send(json.dumps({
            "authorize": token
        }))
        auth_response = await ws.recv()
        auth_data = json.loads(auth_response)
        if "error" in auth_data:
            return {"error": auth_data["error"]["message"]}

        # 2. Place trade on BTCUSDz
        trade_request = {
            "buy": 1,
            "price": 1,  # Amount in USD
            "parameters": {
                "amount": 1,
                "basis": "stake",
                "contract_type": "CALL",  # Use "PUT" for down
                "currency": "USD",
                "duration": 1,
                "duration_unit": "m",
                "symbol": "BTCUSDz"
            }
        }

        await ws.send(json.dumps(trade_request))
        trade_response = await ws.recv()
        return json.loads(trade_response)

# ─────── Discord Command to Trade ─────── #
@bot.command()
async def demo(ctx):
    await ctx.send("Placing trade on BTCUSDz (Deriv demo)...")

    result = await place_btc_trade()
    if "error" in result:
        await ctx.send(f"❌ Trade failed: {result['error']}")
    else:
        contract_id = result["buy"]["contract_id"]
        await ctx.send(f"✅ Trade placed! Contract ID: `{contract_id}`")

# ─────── Run the Bot ─────── #
bot.run(os.getenv("DISCORD_TOKEN"))  # Set this in Render environment

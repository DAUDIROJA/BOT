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
    token = os.getenv("DERIV_TOKEN")

    async with websockets.connect(url) as ws:
        # 1. Authorize
        await ws.send(json.dumps({
            "authorize": token
        }))
        auth_response = await ws.recv()
        auth_data = json.loads(auth_response)

        if "error" in auth_data:
            return {"error": f"[AUTH ERROR] {auth_data['error']['message']}"}

        # 2. Buy contract on BTCUSDz
        buy_request = {
            "buy": 1,
            "price": 1,  # USD
            "parameters": {
                "amount": 1,
                "basis": "stake",
                "contract_type": "CALL",  # "PUT" for sell
                "currency": "USD",
                "duration": 1,
                "duration_unit": "m",
                "symbol": "BTCUSDz"
            }
        }

        await ws.send(json.dumps(buy_request))
        buy_response = await ws.recv()
        buy_data = json.loads(buy_response)

        if "error" in buy_data:
            return {"error": f"[BUY ERROR] {buy_data['error']['message']}"}
        
        return {"success": buy_data["buy"]}

# ─────── Discord Command to Place Trade ─────── #
@bot.command()
async def demo(ctx):
    await ctx.send("Placing trade on BTCUSDz (Deriv demo)...")

    result = await place_btc_trade()

    if "error" in result:
        await ctx.send(f"❌ Trade failed:\n{result['error']}")
    else:
        contract_id = result["success"]["contract_id"]
        buy_price = result["success"]["buy_price"]
        await ctx.send(f"✅ Trade placed!\nContract ID: `{contract_id}`\nBuy Price: ${buy_price}")

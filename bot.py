import discord
from discord.ext import commands
import os
import asyncio
import logging
import MetaTrader5 as mt5
import pandas as pd
import ta
from datetime import datetime
from typing import Optional, Tuple
from telegram.ext import Application, CommandHandler

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PhaseTraderPro:
    def __init__(self, discord_bot=None, telegram_app=None, telegram_chat_id=None):
        self.discord_bot = discord_bot
        self.telegram_app = telegram_app
        self.telegram_chat_id = telegram_chat_id
        self.max_trades_per_phase = None
        self.profit_target_per_phase = None
        self.max_phases = None
        self.base_lot = 0.02
        self.strong_lot = 0.04
        self.strong_move_threshold = 1.8
        self.symbol = "XAUUSD"
        self.current_phase = 1
        self.current_trend = None
        self.active_trades = []
        self.phase_profit = 0
        self.market_status_count = 0
        self.session_start = datetime.now()
        self.running = False
        self.awaiting_input = None

    async def send_message(self, text: str, retries=3, delay=2):
        logger.info(text)
        if self.discord_bot and isinstance(self.discord_bot, commands.Bot):
            for channel in self.discord_bot.get_all_channels():
                if channel.name == "bot-test":  # Adjust channel name as needed
                    await channel.send(text)
                    break
        if self.telegram_app and self.telegram_chat_id:
            for attempt in range(retries):
                try:
                    await self.telegram_app.bot.send_message(chat_id=self.telegram_chat_id, text=text)
                    return
                except Exception as e:
                    logger.error(f"Telegram send error (attempt {attempt + 1}/{retries}): {e}")
                    if attempt < retries - 1:
                        await asyncio.sleep(delay)
            logger.error("Failed to send Telegram message after retries")

    async def initialize(self):
        await self.send_message("🔥 PHASE TRADER PRO v3.4 🔥")
        if not await self.connect_mt5():
            raise Exception("MT5 connection failed")
        await self.send_message("Please send your configuration as:\n/config max_trades profit_target max_phases\nExample: /config 3 6.2 4")
        self.awaiting_input = "config"

    async def connect_mt5(self, retries=3, delay=5):
        for attempt in range(retries):
            try:
                if not mt5.initialize():
                    logger.error("MT5 initialize() failed")
                    await self.send_message("⚠️ MT5 initialize() failed")
                    return False

                authorized = await asyncio.to_thread(
                    mt5.login,
                    login=int(os.getenv("MT5_LOGIN")),
                    password=os.getenv("MT5_PASSWORD"),
                    server=os.getenv("MT5_SERVER", "Deriv-Demo")
                )

                if not authorized:
                    error = mt5.last_error()
                    logger.error(f"MT5 login failed: {error}")
                    await self.send_message(f"⚠️ MT5 login failed. Error: {error}")
                    return False

                if not await asyncio.to_thread(mt5.symbol_select, self.symbol, True):
                    logger.error(f"Symbol {self.symbol} not available")
                    await self.send_message(f"⚠️ Symbol {self.symbol} not available")
                    return False

                await self.send_message("✅ MT5 Connected to Deriv")
                return True
            except Exception as e:
                logger.error(f"Connection error (attempt {attempt + 1}/{retries}): {str(e)}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                continue
        await self.send_message(f"⚠️ Failed to connect to MT5 after {retries} attempts")
        return False

    async def get_equity(self) -> float:
        try:
            account_info = await asyncio.to_thread(mt5.account_info)
            return account_info.equity if account_info else 0
        except Exception as e:
            logger.error(f"Equity fetch error: {str(e)}")
            await self.send_message(f"⚠️ Equity fetch error: {str(e)}")
            return None

    async def handle_config(self, max_trades: str, profit_target: str, max_phases: str):
        try:
            max_trades = int(max_trades)
            profit_target = float(profit_target)
            max_phases = int(max_phases)
            if max_trades <= 0:
                raise ValueError("Max trades must be positive")
            if profit_target <= 0:
                raise ValueError("Profit target must be positive")
            if max_phases <= 0:
                raise ValueError("Max phases must be positive")
            self.max_trades_per_phase = max_trades
            self.profit_target_per_phase = profit_target
            self.max_phases = max_phases
            self.awaiting_input = None
            await self.print_status()
            await self.send_message("✅ Configuration saved! Send /run to begin trading")
        except ValueError as e:
            await self.send_message(f"⚠️ Invalid input: {str(e)}. Example: /config 3 6.2 4")

    async def print_status(self):
        equity = await self.get_equity()
        equity_display = f"${equity:.2f}" if equity is not None else "N/A"
        status_msg = (
            f"\n🔥 PHASE TRADER PRO ACTIVATED 🔥\n"
            f"\n{'#'*20} PHASE {self.current_phase} {'#'*20}\n"
            f"• Target Profit: ${self.profit_target_per_phase}\n"
            f"• Current Phase Profit: ${self.phase_profit:.2f}\n"
            f"• Trades: {len(self.active_trades)}/{self.max_trades_per_phase}\n"
            f"• Max Phases: {self.max_phases if self.max_phases is not None else 'Not set'}\n"
            f"• Account Equity: {equity_display}\n"
            f"• Running since: {self.session_start.strftime('%H:%M:%S')}\n"
            f"{'#'*50}"
        )
        await self.send_message(status_msg)

    async def get_market_data(self, retries=3, delay=5) -> Optional[pd.DataFrame]:
        for attempt in range(retries):
            try:
                rates = await asyncio.to_thread(
                    mt5.copy_rates_from_pos, self.symbol, mt5.TIMEFRAME_M15, 0, 100
                )
                if rates is None or len(rates) == 0:
                    raise ValueError("No data returned from MT5")
                df = pd.DataFrame(rates)
                if 'time' not in df.columns or df.empty:
                    raise ValueError("Invalid data structure")
                df['time'] = pd.to_datetime(df['time'], unit='s', errors='coerce')
                df = df.dropna(subset=['time'])

                df['ema21'] = ta.trend.ema_indicator(df['close'], window=21)
                df['rsi'] = ta.momentum.rsi(df['close'], window=14)
                df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
                df['momentum'] = df['close'].pct_change(3)
                return df.dropna()
            except Exception as e:
                logger.error(f"Data error (attempt {attempt + 1}/{retries}): {str(e)}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                continue
        logger.error("Failed to fetch market data after retries")
        await self.send_message("⚠️ Failed to fetch market data")
        return None

    async def check_conditions(self, df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
        if df is None or df.empty:
            return None, None
        last = df.iloc[-1]
        if last['close'] > last['ema21'] and last['rsi'] > 55:
            strength = 'extreme' if last['momentum'] > (last['atr'] * self.strong_move_threshold) else 'normal'
            return 'bullish', strength
        elif last['close'] < last['ema21'] and last['rsi'] < 45:
            strength = 'extreme' if abs(last['momentum']) > (last['atr'] * self.strong_move_threshold) else 'normal'
            return 'bearish', strength
        return None, None

    async def execute_trade(self, trend_type: str, strength: str) -> bool:
        if len(self.active_trades) >= self.max_trades_per_phase:
            await self.send_message("⚠️ Max trades reached for this phase")
            return False

        try:
            lot_size = self.strong_lot if strength == 'extreme' else self.base_lot
            tick = await asyncio.to_thread(mt5.symbol_info_tick, self.symbol)
            if not tick:
                await self.send_message("⚠️ Failed to get market tick")
                return False
            price = tick.ask if trend_type == 'bullish' else tick.bid
            df = await self.get_market_data()
            if df is None:
                return False
            atr = df['atr'].iloc[-1]

            tp_distance = 3 * atr
            sl_distance = 1.5 * atr
            tp_price = price + tp_distance if trend_type == 'bullish' else price - tp_distance
            sl_price = price - sl_distance if trend_type == 'bullish' else price + sl_distance

            symbol_info = await asyncio.to_thread(mt5.symbol_info, self.symbol)
            if not symbol_info or lot_size < symbol_info.volume_min or lot_size > symbol_info.volume_max:
                await self.send_message(f"⚠️ Invalid lot size: {lot_size}")
                return False

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_BUY if trend_type == 'bullish' else mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 5,
                "magic": 40022024,
                "comment": f"PHASE-{self.current_phase}",
            }

            result = await asyncio.to_thread(mt5.order_send, request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.active_trades.append(result.order)
                trade_msg = (
                    f"\n🚀 NEW {trend_type.upper()} TRADE\n"
                    f"• Price: {price} | Lots: {lot_size}\n"
                    f"• TP: {tp_price:.5f} | SL: {sl_price:.5f} | Phase: {self.current_phase}"
                )
                await self.send_message(trade_msg)
                return True
            else:
                await self.send_message(f"❌ Trade failed: {result.comment}")
                return False
        except Exception as e:
            logger.error(f"Trade execution error: {str(e)}")
            await self.send_message(f"⚠️ Trade execution error: {str(e)}")
            return False

    async def monitor_phase(self):
        try:
            positions = await asyncio.to_thread(mt5.positions_get, symbol=self.symbol)
            self.phase_profit = sum(pos.profit for pos in positions) if positions else 0

            df = await self.get_market_data()
            equity = await self.get_equity()
            equity_display = f"${equity:.2f}" if equity is not None else "N/A"
            if df is not None:
                last = df.iloc[-1]
                self.market_status_count += 1
                await self.send_message(
                    f"\n📊 Market Status #{self.market_status_count}:\n"
                    f"• Price: {last['close']} | EMA21: {last['ema21']:.2f}\n"
                    f"• RSI: {last['rsi']:.1f} | Momentum: {last['momentum']*100:.2f}%\n"
                    f"• Active Trend: {self.current_trend or 'None'}\n"
                    f"• Phase Profit: ${self.phase_profit:.2f}\n"
                    f"• Account Equity: {equity_display}"
                )

            if self.phase_profit >= self.profit_target_per_phase:
                await self.send_message(
                    f"\n🎯 PHASE {self.current_phase} COMPLETED!\nProfit: ${self.phase_profit:.2f}"
                )
                await self.close_all_trades()
                self.active_trades = []

                if self.max_phases is not None and self.current_phase >= self.max_phases:
                    await self.send_message(f"🏁 Max phases ({self.max_phases}) reached! Bot stopped.")
                    self.stop()
                    return True

                self.current_phase += 1
                self.phase_profit = 0
                self.market_status_count = 0
                await self.print_status()
                return True
            return False
        except Exception as e:
            logger.error(f"Monitor phase error: {str(e)}")
            await self.send_message(f"⚠️ Monitor phase error: {str(e)}")
            return False

    async def close_all_trades(self):
        try:
            positions = await asyncio.to_thread(mt5.positions_get, symbol=self.symbol)
            if positions:
                for pos in positions:
                    tick = await asyncio.to_thread(mt5.symbol_info_tick, self.symbol)
                    if not tick:
                        continue
                    close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": self.symbol,
                        "volume": pos.volume,
                        "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                        "position": pos.ticket,
                        "price": close_price,
                        "comment": "PHASE-END",
                    }
                    await asyncio.to_thread(mt5.order_send, request)
                await self.send_message("🛑 All trades closed")
            else:
                await self.send_message("No open positions to close")
        except Exception as e:
            logger.error(f"Close trades error: {str(e)}")
            await self.send_message(f"⚠️ Close trades error: {str(e)}")

    async def run(self):
        if None in (self.max_trades_per_phase, self.profit_target_per_phase, self.max_phases):
            await self.send_message("⚠️ Please configure first with /config")
            return

        self.running = True
        await self.send_message("Time to risk it all 😁😁😁😁😢😢😢")

        try:
            while self.running:
                if self.max_phases is not None and self.current_phase > self.max_phases:
                    await self.send_message(f"🏁 Max phases ({self.max_phases}) reached! Bot stopped.")
                    self.stop()
                    break

                if await self.monitor_phase():
                    if not self.running:
                        break
                    await asyncio.sleep(10)
                    continue

                df = await self.get_market_data()
                if df is None:
                    await asyncio.sleep(10)
                    continue

                trend_type, strength = await self.check_conditions(df)

                if trend_type and trend_type != self.current_trend:
                    self.current_trend = trend_type
                    if self.active_trades:
                        await self.send_message(f"⚠️ Trend changed to {trend_type}, closing existing trades")
                        await self.close_all_trades()
                        self.active_trades = []

                if trend_type and len(self.active_trades) < self.max_trades_per_phase:
                    await self.execute_trade(trend_type, strength)

                await asyncio.sleep(20)
        except Exception as e:
            logger.error(f"Critical error: {str(e)}")
            await self.send_message(f"⚠️ Critical error: {str(e)}")
        finally:
            await asyncio.to_thread(mt5.shutdown)
            await self.send_message("🛑 Trading bot STOPPED")
            self.running = False

    def stop(self):
        self.running = False

async def main():
    # Initialize Discord bot
    intents = discord.Intents.default()
    intents.message_content = True
    discord_bot = commands.Bot(command_prefix="!", intents=intents)

    # Initialize Telegram bot
    telegram_app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    trader = PhaseTraderPro(discord_bot=discord_bot, telegram_app=telegram_app, telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"))

    @discord_bot.event
    async def on_ready():
        print("Discord BOT is ready!")
        await trader.initialize()

    @discord_bot.event
    async def on_message(message):
        if message.author == discord_bot.user:
            return
        content = message.content.lower()
        if trader.awaiting_input == "config" and content.startswith("/config"):
            parts = content.split()
            if len(parts) == 4:
                await trader.handle_config(parts[1], parts[2], parts[3])
        elif content == "/run" and trader.max_trades_per_phase:
            asyncio.create_task(trader.run())
        await discord_bot.process_commands(message)

    # Telegram handlers
    async def start(update, context):
        await trader.send_message("🔥 PHASE TRADER PRO v3.4 🔥\nSend /config max_trades profit_target max_phases to start.")
        trader.awaiting_input = "config"

    async def config(update, context):
        parts = update.message.text.split()
        if len(parts) == 4:
            await trader.handle_config(parts[1], parts[2], parts[3])

    async def run(update, context):
        if trader.max_trades_per_phase:
            asyncio.create_task(trader.run())

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("config", config))
    telegram_app.add_handler(CommandHandler("run", run))

    # Start both bots
    discord_task = asyncio.create_task(discord_bot.start(os.getenv("DISCORD_TOKEN")))
    telegram_task = asyncio.create_task(telegram_app.run_polling())
    await asyncio.gather(discord_task, telegram_task)

if __name__ == "__main__":
    asyncio.run(main())

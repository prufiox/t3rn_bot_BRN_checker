import logging
import asyncio
import aiohttp
import aiosqlite
import re
import time
from decimal import Decimal
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from typing import Any, Awaitable, Callable, Dict
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
API_URL = "https://brn.explorer.caldera.xyz/api/v2/addresses"
DB_PATH = "users.db"
MAX_WALLETS = 5

# Language texts
TEXTS = {
    'ru': {
        'welcome': 'Выберите язык / Choose language:',
        'start_msg': "Привет! Отправь мне T3rn кошелек.\nМожно добавить до {} кошельков.",
        'check_balance': "Проверить балансы",
        'wallet_list': "Список кошельков",
        'auto_check_on': "✅ Включить автопроверку",
        'auto_check_off': "❌ Выключить автопроверку",
        'no_wallets': "У вас нет сохраненных кошельков",
        'getting_info': "Получаю информацию...",
        'wallet_info': "Информация по кошелькам:",
        'wallet': "Кошелек:",
        'balance': "Баланс:",
        'tx_count': "Количество транзакций:",
        'wallet_exists': "Этот кошелек уже добавлен",
        'wallet_limit': "Достигнут лимит в {} кошельков",
        'wallet_saved': "Кошелек сохранен",
        'auto_check_enabled': "Автоматическая проверка балансов включена",
        'auto_check_disabled': "Автоматическая проверка балансов выключена",
        'error_occurred': "Произошла ошибка, попробуйте позже",
    },
    'en': {
        'welcome': 'Choose language / Выберите язык:',
        'start_msg': "Hello! Send me your T3rn wallet.\nYou can add up to {} wallets.",
        'check_balance': "Check balances",
        'wallet_list': "Wallet list",
        'auto_check_on': "✅ Enable auto-check",
        'auto_check_off': "❌ Disable auto-check",
        'no_wallets': "You have no saved wallets",
        'getting_info': "Getting information...",
        'wallet_info': "Wallet information:",
        'wallet': "Wallet:",
        'balance': "Balance:",
        'tx_count': "Transaction count:",
        'wallet_exists': "This wallet is already added",
        'wallet_limit': "Reached the limit of {} wallets",
        'wallet_saved': "Wallet saved",
        'auto_check_enabled': "Automatic balance check enabled",
        'auto_check_disabled': "Automatic balance check disabled",
        'error_occurred': "An error occurred, please try again later",
    }
}

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()


class RateLimiterMiddleware:
    def __init__(self, rate_limit: float):
        self.rate_limit = rate_limit
        self.last_message_time = {}

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            message: Message,
            data: Dict[str, Any]
    ) -> Any:
        if not message.from_user:
            return await handler(message, data)

        user_id = message.from_user.id
        current_time = time.time()

        if user_id in self.last_message_time:
            time_passed = current_time - self.last_message_time[user_id]
            if time_passed < self.rate_limit:
                delay = self.rate_limit - time_passed
                logger.info(f"Rate limit hit for user {user_id}, waiting {delay:.2f}s")
                await asyncio.sleep(delay)

        self.last_message_time[user_id] = current_time
        return await handler(message, data)


def get_main_keyboard(is_auto_check: bool, lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXTS[lang]['check_balance'])],
            [KeyboardButton(text=TEXTS[lang]['wallet_list'])],
            [KeyboardButton(text=TEXTS[lang]['auto_check_off'] if is_auto_check else TEXTS[lang]['auto_check_on'])],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
               CREATE TABLE IF NOT EXISTS users (
                   user_id INTEGER PRIMARY KEY,
                   language TEXT DEFAULT 'en'
               )
           """)
            await db.execute("""
               CREATE TABLE IF NOT EXISTS wallets (
                   user_id INTEGER,
                   wallet TEXT,
                   auto_check INTEGER DEFAULT 0,
                   PRIMARY KEY (user_id, wallet)
               )
           """)
            await db.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


async def get_user_language(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT language FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 'en'


async def get_user_wallets(user_id: int) -> list:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT wallet FROM wallets WHERE user_id = ?",
                (user_id,)
            )
            wallets = await cursor.fetchall()
            return [wallet[0] for wallet in wallets]
    except Exception as e:
        logger.error(f"Error getting wallets for user {user_id}: {e}")
        return []


async def get_wallet_info(wallet: str, lang: str) -> str:
    retries = 3
    for attempt in range(retries):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Get balance
                async with session.get(f"{API_URL}/{wallet}") as resp:
                    if resp.status != 200:
                        logger.warning(f"API returned status {resp.status} for wallet {wallet}")
                        if attempt < retries - 1:
                            await asyncio.sleep(1 * (attempt + 1))
                            continue
                        return f"{TEXTS[lang]['error_occurred']}"
                    data = await resp.json()
                    balance = Decimal(data.get('coin_balance', 0)) / Decimal('1000000000000000000')

                # Get transaction count
                async with session.get(f"{API_URL}/{wallet}/counters") as response:
                    if response.status == 200:
                        counters = await response.json()
                        tx_count = counters.get("transactions_count", "0")
                    else:
                        tx_count = "N/A"

                return (
                    f"{TEXTS[lang]['wallet']} {wallet}\n"
                    f"{TEXTS[lang]['balance']} {balance:.6f} BRN\n"
                    f"{TEXTS[lang]['tx_count']} {tx_count}"
                )
        except Exception as e:
            logger.error(f"Error fetching wallet {wallet} (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(1 * (attempt + 1))
                continue
            return f"{TEXTS[lang]['error_occurred']}"


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
        ]
    ])
    await message.answer(TEXTS['en']['welcome'], reply_markup=keyboard)


@dp.callback_query(F.data.startswith("lang_"))
async def callback_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)",
            (callback.from_user.id, lang)
        )
        await db.commit()

    await callback.message.delete()
    await callback.message.answer(
        TEXTS[lang]['start_msg'].format(MAX_WALLETS),
        reply_markup=get_main_keyboard(False, lang)
    )


@dp.message(F.text)
async def handle_text(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    text = message.text

    # Handle check balances command
    if text == TEXTS[lang]['check_balance'] or text == TEXTS['en']['check_balance'] or text == TEXTS['ru'][
        'check_balance']:
        await cmd_check(message)
        return

    # Handle wallet list command
    if text == TEXTS[lang]['wallet_list'] or text == TEXTS['en']['wallet_list'] or text == TEXTS['ru']['wallet_list']:
        await cmd_list(message)
        return

    # Handle auto-check commands
    if any(text == t for t in [
        TEXTS[lang]['auto_check_on'], TEXTS[lang]['auto_check_off'],
        TEXTS['en']['auto_check_on'], TEXTS['en']['auto_check_off'],
        TEXTS['ru']['auto_check_on'], TEXTS['ru']['auto_check_off']
    ]):
        await cmd_check_interval(message)
        return

    # Handle wallet address
    if re.match(r'^0x[a-fA-F0-9]{40}$', text):
        await handle_wallet(message)
        return


async def cmd_check(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    try:
        wallets = await get_user_wallets(message.from_user.id)
        if not wallets:
            await message.answer(
                TEXTS[lang]['no_wallets'],
                reply_markup=get_main_keyboard(False, lang)
            )
            return

        status = await message.answer(TEXTS[lang]['getting_info'])
        info = f"{TEXTS[lang]['wallet_info']}\n\n"

        for wallet in wallets:
            wallet_info = await get_wallet_info(wallet, lang)
            info += f"{wallet_info}\n\n"

        await status.delete()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT DISTINCT auto_check FROM wallets WHERE user_id = ?",
                (message.from_user.id,)
            )
            row = await cursor.fetchone()
            is_auto_check = row[0] if row else 0

        await message.answer(info, reply_markup=get_main_keyboard(is_auto_check, lang))
        logger.info(f"Balance check completed for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error checking balances: {e}")
        await message.answer(TEXTS[lang]['error_occurred'])


async def cmd_list(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    try:
        wallets = await get_user_wallets(message.from_user.id)
        if not wallets:
            await message.answer(
                TEXTS[lang]['no_wallets'],
                reply_markup=get_main_keyboard(False, lang)
            )
            return

        text = f"{TEXTS[lang]['wallet_list']}:\n\n"
        for i, wallet in enumerate(wallets, 1):
            text += f"{i}. {wallet}\n"

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT DISTINCT auto_check FROM wallets WHERE user_id = ?",
                (message.from_user.id,)
            )
            row = await cursor.fetchone()
            is_auto_check = row[0] if row else 0

        await message.answer(text, reply_markup=get_main_keyboard(is_auto_check, lang))
        logger.info(f"Wallet list displayed for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error listing wallets: {e}")
        await message.answer(TEXTS[lang]['error_occurred'])


async def cmd_check_interval(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT DISTINCT auto_check FROM wallets WHERE user_id = ?",
                (message.from_user.id,)
            )
            row = await cursor.fetchone()
            current_status = row[0] if row else 0

            new_status = 0 if current_status else 1

            await db.execute(
                "UPDATE wallets SET auto_check = ? WHERE user_id = ?",
                (new_status, message.from_user.id)
            )
            await db.commit()

        status_text = TEXTS[lang]['auto_check_enabled'] if new_status else TEXTS[lang]['auto_check_disabled']
        await message.answer(
            status_text,
            reply_markup=get_main_keyboard(new_status, lang)
        )
        logger.info(f"Auto-check status changed to {new_status} for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error changing auto-check status: {e}")
        await message.answer(TEXTS[lang]['error_occurred'])


async def handle_wallet(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT DISTINCT auto_check FROM wallets WHERE user_id = ?",
                (message.from_user.id,)
            )
            row = await cursor.fetchone()
            is_auto_check = row[0] if row else 0

        wallets = await get_user_wallets(message.from_user.id)
        if message.text in wallets:
            await message.answer(
                TEXTS[lang]['wallet_exists'],
                reply_markup=get_main_keyboard(is_auto_check, lang)
            )
            return

        if len(wallets) >= MAX_WALLETS:
            await message.answer(
                TEXTS[lang]['wallet_limit'].format(MAX_WALLETS),
                reply_markup=get_main_keyboard(is_auto_check, lang)
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO wallets (user_id, wallet, auto_check) VALUES (?, ?, ?)",
                (message.from_user.id, message.text, is_auto_check)
            )
            await db.commit()

        info = await get_wallet_info(message.text, lang)
        await message.answer(
            f"{info}\n{TEXTS[lang]['wallet_saved']}",
            reply_markup=get_main_keyboard(is_auto_check, lang)
        )
        logger.info(f"New wallet added for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error handling wallet: {e}")
        await message.answer(TEXTS[lang]['error_occurred'])


async def periodic_check():
    while True:
        try:
            users_to_check = []
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("""
                    SELECT DISTINCT w.user_id, w.wallet, u.language 
                    FROM wallets w
                    LEFT JOIN users u ON w.user_id = u.user_id
                    WHERE w.auto_check = 1
                """)
                users_wallets = await cursor.fetchall()
                users_to_check = users_wallets

            logger.info(f"Starting periodic check for {len(users_to_check)} wallets")

            # Process in chunks of 10 wallets
            chunk_size = 10
            for i in range(0, len(users_to_check), chunk_size):
                chunk = users_to_check[i:i + chunk_size]
                for user_id, wallet, lang in chunk:
                    try:
                        wallet_info = await get_wallet_info(wallet, lang or 'en')
                        await bot.send_message(
                            user_id,
                            f"{TEXTS[lang or 'en']['wallet_info']}\n\n{wallet_info}"
                        )
                        await asyncio.sleep(2)  # Delay between messages
                    except Exception as e:
                        logger.error(f"Error checking wallet for user {user_id}: {e}")

                await asyncio.sleep(5)  # Delay between chunks

            logger.info("Periodic check completed")
            await asyncio.sleep(1800)  # 30 minutes between checks
        except Exception as e:
            logger.error(f"Error in periodic check: {e}")
            await asyncio.sleep(60)


async def main():
    try:
        await init_db()

        # Add rate limiter
        dp.message.middleware(RateLimiterMiddleware(rate_limit=1))

        periodic_task = asyncio.create_task(periodic_check())

        logger.info("Bot started")
        await dp.start_polling(bot,
                               allowed_updates=["message", "callback_query"],
                               polling_timeout=30
                               )
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        logger.info("Bot stopped")
        periodic_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

# T3rn Balance Checker Bot

A Telegram bot for monitoring T3rn wallet balances and transactions with multi-language support and automated checking features.

## 🚀 Features

### 🌍 Multi-Language Support

- 🇬🇧 English
- 🇷🇺 Russian
- Easy to add new languages

### 💼 Wallet Management

- Add up to **5 wallets** per user
- 🔄 Real-time balance checking
- 📊 Transaction count monitoring
- 📋 Wallet list management

### 🔧 Automated Features

- ⏰ **Automatic balance checking** (30-minute intervals)
- 🔔 **Balance change notifications**
- 🛡️ **Built-in rate limiting and spam protection**

### 🏗️ Technical Features

- ⚡ **Asynchronous architecture**
- 📦 **SQLite database for data persistence**
- 🔒 **Error handling and retry mechanisms**
- 📝 **Comprehensive logging**

---

## 📦 Installation

### Prerequisites

- Python **3.8+**
- A Telegram Bot Token (Get it from [@BotFather](https://t.me/botfather))

### Setup Steps

```bash
# 1. Clone the repository
git clone https://github.com/prufiox/t3rn-balance-bot.git
cd t3rn-balance-bot

# 2. Create and activate a virtual environment
# Linux/macOS
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a .env file and add your bot token
echo "TELEGRAM_TOKEN=your_bot_token_here" > .env

# 5. Run the bot
python main.py
```

---

## 📖 Usage

1. **Start a chat** with the bot on Telegram.
2. **Send** `/start` to begin.
3. **Choose** your preferred language.
4. **Add** your T3rn wallet addresses.

### 📜 Available Commands

- `/start` - Start the bot and select language

#### 🖱️ Button Commands:

- **"Check balances"** - Get current balances for all wallets
- **"Wallet list"** - View all added wallets
- **"Enable/Disable auto-check"** - Toggle automatic balance checking

---

## ⏳ Auto-Check Feature

The bot automatically checks balances every **30 minutes** and notifies you of any changes.
To enable this feature:

1. Add at least **one wallet**.
2. Click the **"Enable auto-check"** button.
3. Receive periodic updates.

---

## ⚙️ Configuration

### 🔢 Main Settings in Code:

```python
MAX_WALLETS = 5  # Maximum wallets per user
API_URL = "https://brn.explorer.caldera.xyz/api/v2/addresses"  # API endpoint
```

### 🗄️ Database Structure

```sql
-- Users table (language preferences)
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'en'
);

-- Wallets table
CREATE TABLE wallets (
    user_id INTEGER,
    wallet TEXT,
    auto_check INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, wallet)
);
```

---

## 🌍 Adding New Languages

To add a new language, update the `TEXTS` dictionary in `main.py`:

```python
TEXTS = {
    'new_lang': {
        'welcome': 'Welcome message',
        # ... other translations
    }
}
```

---

## 🛠️ Error Handling

- **API connection retries**
- **Rate limiting protection**
- **Database transaction safety**
- **User input validation**

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create a feature branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to branch** (`git push origin feature/AmazingFeature`)
5. **Open Pull Request**

---

## 📋 Requirements

```txt
aiogram>=3.0.0
aiohttp>=3.8.0
aiosqlite>=0.17.0
python-dotenv>=0.19.0
```

---

## 📜 License

MIT License. See **LICENSE** for details.

---

## 📞 Contact

- **Project Link**: [GitHub Repo](https://github.com/prufiox/t3rn-balance-bot)

---

## 💡 Acknowledgments

- **T3rn Network**
- **Aiogram**

---

## 📅 Changelog

### [1.0.0] - 2025-01-29

- Initial release
- Multi-language support (EN/RU)
- Basic wallet management
- Auto-check feature


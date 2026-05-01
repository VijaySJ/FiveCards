# 🃏 5 Cards — Telegram Group Card Game Bot

A fun, multiplayer card game bot for Telegram groups! Players take turns picking, drawing, and discarding cards to get the lowest score. Declare when you think you have the best hand — but beware the 80-point penalty if someone beats you!

## 📋 Prerequisites

- **Python 3.11+** installed
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
  1. Open Telegram, search for `@BotFather`
  2. Send `/newbot` and follow the prompts
  3. Copy the token (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
  4. **Important**: Enable inline mode and group privacy settings if needed

## 🚀 Installation

```bash
# Clone or download the project
cd fivecards_bot

# Install dependencies
pip install -r requirements.txt

# Copy the example config and add your bot token
cp .env.example .env
# Edit .env and paste your BOT_TOKEN
```

## ⚙️ .env Configuration

```env
BOT_TOKEN=your_telegram_bot_token_here
MAX_PLAYERS=10
DEFAULT_ROUNDS=3
MAX_ROUNDS=10
CARDS_PER_PLAYER=5
LOG_LEVEL=INFO
```

## ▶️ Running Locally

```bash
python run.py
```

The bot starts in **polling mode** — it checks Telegram for updates regularly. No webhook setup needed.

## ☁️ Deploy to Railway

1. Push your code to a GitHub repo
2. Go to [Railway.app](https://railway.app/) → **New Project** → **Deploy from GitHub**
3. Add environment variable: `BOT_TOKEN=your_token`
4. Railway auto-detects the `Procfile` and starts the bot

## 🎮 Command Reference

| Command | Who | Description |
|---|---|---|
| `/newgame [N]` | Anyone | Create a new game (N = rounds, default 3) |
| `/join` | Anyone | Join the game lobby |
| `/startgame` | Admin | Deal cards and start playing (min 2 players) |
| `/pick` | Active player | Pick the top card from the discard pile |
| `/draw` | Active player | Draw a card from the deck |
| `/drop <cards>` | Active player | Discard card(s), e.g. `/drop 6H` or `/drop 6H 6D` |
| `/declare` | Active player | Declare (attempt to win the round) |
| `/hand` | Any player | View your hand (sent via DM) |
| `/scores` | Anyone | Show current scores |
| `/endgame` | Admin | Force-end the game |
| `/help` | Anyone | Show help and rules |

## 🎯 How to Play

### Setup
1. Add the bot to a Telegram group
2. **Every player must DM the bot first** (click the bot name → START)
3. Someone types `/newgame 3` (for 3 rounds)
4. Others type `/join` to enter
5. Admin types `/startgame` to deal cards

### Each Turn
1. **Choose one action**:
   - 🃏 **Pick** the open (top discard) card
   - 🎴 **Draw** from the deck
   - 🏳️ **Declare** (end the round)

2. **After Pick/Draw**: You must discard one or more cards
   - `/drop 6H` — drop one card
   - `/drop 6H 6D 6C` — drop multiple cards (must be same rank!)

3. **Group Drop**: If you pick a card and hold 2+ cards of the same rank (including the picked card), ALL matching cards are dropped automatically!

### Winning
- Lowest total score across all rounds wins! 🥇
- Highest score loses 💀

## 📊 Point System

| Card | Points |
|---|---|
| A | 1 |
| 2–10 | Face value |
| J | 11 |
| Q | 12 |
| K | 13 |
| Printed Joker (🃏) | 0 |
| Joker-rank cards | 0 |

**Joker Rank**: After dealing, one card is drawn — its rank becomes the "joker rank" for that round. All cards of that rank are worth **0 points**.

## 🏳️ Declaration Scoring

When a player declares, all hands are revealed and scored:

### Rule 1 — Declarer Wins
If the declarer's hand value is **strictly lower** than all opponents:
- Declarer → **0 points** ✨
- Others → their hand value

### Rule 2 — Declarer Penalty
If **any** opponent has a **lower** hand value than the declarer:
- Declarer → **80 points** ⚠️ (penalty!)
- Others → their hand value

### Rule 3 — Tie
If an opponent **ties** with the declarer (and no one is lower):
- Both → **0 points**
- Others → their hand value

### Rule 4 — Empty Hand
A player with **0 cards** in hand → **always 0 points**, regardless of other rules.

> **Priority**: Rule 2 > Rule 3 > Rule 1. Rule 4 always applies.

### Example Scenario

```
Joker rank: 6 (all 6s = 0 points)

Vijay:  KS(13) 3C(3) AS(1) = 17 pts
Ravi:   2H(2) 4D(4) 7S(7) JC(11) QH(12) = 36 pts [DECLARES]
Meena:  9C(9) 5H(5) KD(13) 10S(10) 3H(3) = 40 pts

Vijay (17) < Ravi (36) → RULE 2 applies!

Results:
  Vijay  = 17 pts
  Ravi   = 80 pts (penalty!)
  Meena  = 40 pts
```

## 🃏 Deck Scaling

The number of card decks scales with player count:
- **2–7 players** → 1 deck (54 cards)
- **8–10 players** → 2 decks (108 cards)

This ensures enough cards in the draw pile for larger games.

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

## 📁 Project Structure

```
fivecards_bot/
├── run.py                        ← Entry point: python run.py
├── app/                          ← Main application package
│   ├── __init__.py
│   ├── main.py                   ← App builder & handler registration
│   │
│   ├── config/                   ← Configuration layer
│   │   ├── __init__.py
│   │   └── settings.py           ← Env vars, constants, logging
│   │
│   ├── core/                     ← Pure game logic (no Telegram)
│   │   ├── __init__.py
│   │   ├── card_utils.py         ← Deck, shuffle, deal, formatting
│   │   ├── game_engine.py        ← Game flow orchestration
│   │   ├── score_engine.py       ← Scoring rules & leaderboard
│   │   └── exceptions.py         ← Custom game exceptions
│   │
│   ├── bot/                      ← Telegram-specific layer
│   │   ├── __init__.py
│   │   ├── commands.py           ← /command handlers
│   │   ├── callbacks.py          ← Inline button callback handler
│   │   ├── keyboards.py          ← InlineKeyboardMarkup builders
│   │   └── helpers.py            ← DM sending & bot helpers
│   │
│   └── services/                 ← Shared services
│       ├── __init__.py
│       ├── state_manager.py      ← In-memory game state CRUD
│       └── message_formatter.py  ← Message text builders
│
├── tests/                        ← Unit tests
│   ├── __init__.py
│   ├── conftest.py               ← Shared test fixtures
│   ├── test_card_utils.py
│   ├── test_game_engine.py
│   └── test_score_engine.py
│
├── .env.example                  ← Config template
├── requirements.txt              ← Dependencies
├── Procfile                      ← Deployment config
└── README.md                     ← This file
```

## 📝 License

MIT License — feel free to modify and deploy!

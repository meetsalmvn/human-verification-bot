# 🛡 Human Verification Telegram Bot

A production-ready Telegram bot that automatically verifies users requesting
to join a private group using Telegram's **Join Request** feature, before
approving or declining them — powered by **aiogram 3**, **aiohttp**, and
**SQLite**.

---

## ✨ Features

- **Automatic join-request handling** — detects every request to join your
  private group.
- **Four challenge types**: math, emoji selection, button captcha, and word
  selection — chosen randomly or fixed via config.
- **Configurable timeout** (default 60s) and **attempt limit** (default 3).
- **Auto-approve / auto-decline** based on the outcome.
- **Whitelist & blacklist** — always approve or always reject specific users.
- **Maintenance mode** — pause automated decisions without losing requests.
- **Admin panel**: `/stats`, interactive `/config` menu, `/logs`, `/export`,
  `/help`.
- **Replay-attack resistant** — single-use, token-based verification
  sessions with constant-time comparison.
- **Rate limiting** on messages and callback queries.
- **Restart recovery** — in-flight verification timeouts are resumed (or
  safely expired) after a redeploy/crash.
- **Webhook or long-polling**, a `/health` endpoint, and a ready-to-use
  `Dockerfile` for Northflank or any container platform.

---

## 🏗 Architecture

```
human-verification-bot/
├── app/
│   ├── main.py                  # Entrypoint (webhook or polling)
│   ├── bot.py                   # Bot + Dispatcher factory, middleware wiring
│   ├── config/
│   │   └── settings.py          # Env-driven Settings dataclass
│   ├── database/
│   │   ├── db.py                # aiosqlite Database class (schema + queries)
│   │   └── models.py            # Row dataclasses
│   ├── handlers/
│   │   ├── join_requests.py     # ChatJoinRequest -> VerificationService
│   │   ├── verification.py      # /start + challenge callback answers
│   │   ├── admin.py             # /stats /config /logs /export /whitelist ...
│   │   └── common.py            # Fallbacks / non-admin denial messages
│   ├── middlewares/
│   │   ├── throttling.py        # Per-user rate limiting
│   │   └── error_logging.py     # Catches unhandled exceptions
│   ├── services/
│   │   ├── challenge_service.py # Generates math/emoji/button/word challenges
│   │   ├── verification_service.py # Core orchestration, approve/decline, timeouts
│   │   └── stats_service.py     # Aggregates /stats numbers
│   ├── keyboards/
│   │   ├── verification_kb.py   # Challenge inline keyboards
│   │   └── admin_kb.py          # /config inline menus
│   └── utils/
│       ├── logger.py            # Logging setup
│       ├── security.py          # Token generation, constant-time compare
│       └── texts.py             # All user-facing copy (dark-styled HTML)
├── data/                        # SQLite database lives here (volume-mounted)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

### Flow overview

1. A user sends a **join request** to your private group.
2. The bot stores a `pending_requests` row and tries to DM the user. If
   they've never started the bot, Telegram blocks the message — the bot
   logs this and waits.
3. The user presses **Start** in their private chat with the bot
   (`/start`, optionally via a `t.me/<bot>?start=verify` deep link you put
   in your group's join-request instructions).
4. The bot generates a random challenge, stores a single-use
   `verification_sessions` token, and sends an inline keyboard. A timeout
   task is scheduled in parallel.
5. On a correct answer → the join request is **approved** and the token is
   invalidated. On 3 incorrect answers, or if the timer runs out → the
   request is **declined**.

---

## 🚀 Local installation

**Requirements:** Python 3.12+, a Telegram bot token from
[@BotFather](https://t.me/BotFather).

```bash
git clone <your-repo-url> human-verification-bot
cd human-verification-bot

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env: BOT_TOKEN, ADMIN_IDS, GROUP_ID, BOT_USERNAME, USE_WEBHOOK=false

python -m app.main
```

With `USE_WEBHOOK=false`, the bot uses long polling — nothing else to
configure locally.

### Telegram group setup

1. Add your bot to the group as an **administrator**.
2. Enable **"Approve new members"** (join requests) in the group's member
   permissions.
3. Make sure the bot has the **"Add users"/"Invite via link"** admin
   permission that allows it to approve/decline join requests.
4. Set `GROUP_ID` in `.env` to the group's numeric chat ID (use
   [@userinfobot](https://t.me/userinfobot) or your own logging to find it —
   it will look like `-1001234567890`).

---

## 🐳 Docker usage

```bash
cp .env.example .env
# fill in .env, then:

docker compose up --build -d
docker compose logs -f
```

The container exposes port `8080` with a `/health` endpoint and persists the
SQLite database in the `bot_data` named volume (`/app/data` inside the
container).

To run the image directly instead of via compose:

```bash
docker build -t human-verification-bot .
docker run -d --name hvbot \
  --env-file .env \
  -p 8080:8080 \
  -v hvbot_data:/app/data \
  human-verification-bot
```

---

## ☁️ Northflank deployment

1. **Create a new service** in Northflank from this repository (or push the
   built image to a registry and deploy from image).
2. **Build type:** Dockerfile (uses the included `Dockerfile`).
3. **Port:** expose port `8080` (HTTP), and set it as the service's public
   port.
4. **Persistent volume:** attach a volume mounted at `/app/data` so the
   SQLite database survives restarts/redeploys.
5. **Environment variables:** add everything from `.env.example` under the
   service's *Environment* tab, in particular:
   - `BOT_TOKEN`
   - `ADMIN_IDS`
   - `GROUP_ID`
   - `BOT_USERNAME`
   - `USE_WEBHOOK=true`
   - `WEBHOOK_HOST` — set this to the **public HTTPS URL** Northflank
     assigns to the service (e.g. `https://human-verification-bot--xxxx.code.run`)
   - `WEBHOOK_SECRET` — any random string, used to validate incoming webhook
     calls actually come from Telegram
   - `PORT=8080` (Northflank typically injects `PORT` automatically — make
     sure it matches the exposed port)
6. **Health check:** point Northflank's health check at `GET /health` on
   port `8080`.
7. Deploy. On startup the bot automatically calls `setWebhook` against
   `WEBHOOK_HOST + WEBHOOK_PATH`, so no manual `setWebhook` call is needed.

---

## ⚙️ Environment variables

| Variable                     | Required | Default        | Description                                             |
|-------------------------------|:--------:|----------------|-----------------------------------------------------------|
| `BOT_TOKEN`                   | ✅       | —              | Token from @BotFather                                     |
| `ADMIN_IDS`                   | ✅       | —              | Comma-separated Telegram user IDs with admin access        |
| `GROUP_ID`                    | ✅       | —              | Numeric chat ID of the protected group                    |
| `BOT_USERNAME`                | ✅       | —              | Bot's `@username` (no `@`), used for deep links            |
| `USE_WEBHOOK`                 |          | `true`         | `true` = webhook mode, `false` = long polling              |
| `WEBHOOK_HOST`                | webhook  | —              | Public HTTPS base URL                                      |
| `WEBHOOK_PATH`                |          | `/webhook`     | Path Telegram will POST updates to                         |
| `WEBHOOK_SECRET`              |          | —              | Optional secret token validated on every webhook call       |
| `WEBAPP_HOST`                 |          | `0.0.0.0`      | Bind address for the aiohttp server                        |
| `PORT`                        |          | `8080`         | Bind port for the aiohttp server                            |
| `DB_PATH`                     |          | `./data/bot.db`| SQLite file path                                            |
| `VERIFICATION_TIMEOUT`        |          | `60`           | Seconds before a challenge expires                          |
| `MAX_ATTEMPTS`                |          | `3`            | Allowed wrong answers before decline                        |
| `DEFAULT_CHALLENGE_TYPE`      |          | `random`       | `random`, `math`, `emoji`, `button`, or `word`              |
| `RATE_LIMIT_WINDOW_SECONDS`   |          | `1.0`          | Minimum seconds between actions per user                    |
| `LOG_LEVEL`                   |          | `INFO`         | Python logging level                                        |
| `MAINTENANCE_MODE`            |          | `false`        | Pauses automatic approve/decline while `true`               |

Runtime-tunable values (`verification_timeout`, `max_attempts`,
`challenge_type`, `verification_enabled`, `maintenance_mode`) can also be
changed live from Telegram via `/config`, without a redeploy — they're
stored in the `settings` table and override the environment defaults.

---

## 🔐 Security notes

- Verification tokens are generated with `secrets.token_urlsafe` (CSPRNG),
  are single-use, and are compared with `hmac.compare_digest` to avoid
  timing attacks.
- Every session is tied to a specific `user_id`; a callback from any other
  user is rejected even if they somehow obtain the token.
- Expired or already-resolved sessions are rejected immediately ("session no
  longer valid") rather than silently reprocessed.
- A per-user rate limiter throttles rapid-fire messages/callbacks.
- Blacklisted users are auto-declined before a challenge is ever generated;
  whitelisted users are auto-approved.

---

## 🖼 Screenshots

> _Add screenshots of the verification prompt, success/failure states, and
> the admin `/config` panel here._

- `docs/screenshot-challenge.png`
- `docs/screenshot-success.png`
- `docs/screenshot-config.png`

---

## 🗺 Future improvements

- Localization (multi-language `texts.py` loader keyed by user locale)
- Redis-backed rate limiting and session storage for multi-instance scaling
- PostgreSQL support for larger deployments
- Per-group configuration (currently one group per bot instance)
- Captcha difficulty presets (easy/medium/hard) exposed in `/config`
- Invite-link tracking and per-invite analytics
- Admin web dashboard

---

## 📄 License

MIT — do whatever you like, no warranty provided.

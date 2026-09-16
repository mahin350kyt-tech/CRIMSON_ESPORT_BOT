# CRIMSON ESPORT Discord Bot

This is a beginner-friendly Discord bot starter with:
- 🎫 Persistent ticket panel + private tickets
- 🔒 Ticket close/delete with staff access
- 🛠️ Staff commands: kick, ban, timeout, clear, warn, warnings, lock, unlock
- 📋 Application panel + modal
- 📜 Logs for joins/leaves, deleted/edited messages, moderation, tickets and applications
- 👋 Welcome messages
- ⚡ Custom text commands
- 🏓 Ping + server info
- 💾 SQLite database for warnings/custom commands
- 🟢 Designed to run continuously on a persistent hosting service

## Local test

1. Install Python 3.11+.
2. Run: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`.
4. Put your bot token in `.env`.
5. Put your server ID in `GUILD_ID`.
6. Run: `python bot.py`

## First Discord setup

The bot needs permissions such as View Channels, Send Messages, Embed Links, Read Message History, Manage Channels, Manage Messages, Manage Roles, Kick Members, Ban Members, Moderate Members.

The bot also needs the Message Content and Server Members privileged intents enabled in the Discord Developer Portal.

After it is online:
1. Run `/setup` as staff.
2. Run `/ticket_panel` where you want the ticket panel.
3. Run `/application_panel` where you want the application panel.
4. Optionally set `STAFF_ROLE_ID` and the channel IDs in `.env`.

## Important security

Never send your bot token to anyone or commit `.env` to GitHub. If a token is exposed, regenerate it immediately in the Discord Developer Portal.

## 24/7 hosting

Use a persistent service such as Railway. Connect the project/repository, set `DISCORD_TOKEN` and the other variables in the service Variables section, and use `python bot.py` as the start command if Railway does not detect it automatically.

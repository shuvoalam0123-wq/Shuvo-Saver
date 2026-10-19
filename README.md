# Video Downloader Saver — Telegram Bot

**Created by Shuvo Chowdhury**

A Telegram bot starter that detects a URL in a message and offers video quality or MP3 options. Uses `yt-dlp` for supported, accessible public links and FFmpeg for audio conversion/format merging.

## Features
- Automatic URL detection
- Multiple sites supported by the installed `yt-dlp` version (not every site/link is guaranteed)
- 360p / 720p / 1080p options where available
- MP3 audio option
- Status and error messages
- Admin-only `/stats`
- Configurable file size and concurrent-download limits
- Polling worker suitable for always-on hosting

## Important limits
- Only download content you own or are authorized to save. Respect copyright and platform terms.
- Private, login-gated, DRM-protected, region-restricted, or otherwise blocked content may fail. Do not add cookies or bypass access controls.
- Telegram Bot API upload limits depend on the API/server setup. This template defaults to 49 MB for compatibility; larger files may fail.
- 24/7 operation depends on a hosting plan that supports always-on workers. Free plans may sleep or stop workers.
- `/stats` reports configured runtime information, not a persistent analytics database. Broadcast and user tracking are not enabled in this starter.
- This project cannot save directly to a user's iPhone Photos library. It sends the file to Telegram; the user taps Share → Save Video.

## Setup
1. Create a bot with `@BotFather` and copy its token.
2. Create a GitHub repository and upload these files. Never commit `.env` or your bot token.
3. In the hosting dashboard, connect the repository and create a **worker/background service** (not a static website).
4. Add environment variables:
   - `TELEGRAM_BOT_TOKEN`: token from BotFather
   - `ADMIN_IDS`: your numeric Telegram user ID (not your username)
   - `MAX_FILE_MB`: `49`
   - `MAX_CONCURRENT_DOWNLOADS`: `2`
5. Use the Dockerfile build if supported; it installs FFmpeg. Otherwise use `pip install -r requirements.txt` and ensure FFmpeg is installed.
6. Deploy and inspect logs. Open the bot in Telegram and send `/start`.
7. Send a permitted public video link, then choose a format.

## Commands
- `/start` — welcome and usage
- `/help` — instructions
- `/stats` — admin-only runtime configuration

## Set your Telegram admin ID
Message a trusted Telegram ID lookup bot or use your own Telegram update logs to find your numeric ID. Verify it before adding it to `ADMIN_IDS`. Do not share your bot token in chat or screenshots.

## Troubleshooting
- `TELEGRAM_BOT_TOKEN` missing: set it in hosting Secrets/Environment Variables.
- `ffmpeg not found`: deploy with the included Dockerfile or install FFmpeg on the host.
- Bot goes offline: check whether the host supports an always-on worker and whether the service has exceeded its quota.
- A specific site fails: update `yt-dlp` and test another accessible public URL; platform changes can temporarily break support.
- File too large: choose a lower resolution or lower `MAX_FILE_MB` to match the host/API limits.

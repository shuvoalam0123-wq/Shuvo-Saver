import os
import re
import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_NAME = "Video Downloader Saver"
CREATOR = "Shuvo Chowdhury"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "49"))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024
MAX_CONCURRENT = max(1, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2")))
SUPPORTED_HINT = "Supported public links may include YouTube, TikTok, Instagram, Facebook and other sites supported by yt-dlp. Some links may fail due to platform restrictions."
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger("video-downloader")
semaphore = asyncio.Semaphore(MAX_CONCURRENT)
URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def safe_url(text: str):
    match = URL_RE.search(text or "")
    if not match:
        return None
    url = match.group(0).rstrip(".,!?)\u3002")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return url

def ydl_options(mode="best", outtmpl=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": True,
        "socket_timeout": 25,
        "retries": 2,
        "fragment_retries": 2,
        "max_filesize": MAX_FILE_BYTES,
        "outtmpl": outtmpl or "%(title).80s-%(id)s.%(ext)s",
        "merge_output_format": "mp4",
    }
    if mode == "audio":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    elif mode == "360":
        opts["format"] = "best[height<=360]/best"
    elif mode == "720":
        opts["format"] = "best[height<=720]/best"
    elif mode == "1080":
        opts["format"] = "best[height<=1080]/best"
    else:
        opts["format"] = "best[ext=mp4][height<=720]/best[height<=720]/best"
    return opts

def download_media(url: str, mode: str, folder: str):
    template = str(Path(folder) / "%(title).70s-%(id)s.%(ext)s")
    with yt_dlp.YoutubeDL(ydl_options(mode, template)) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if mode == "audio":
            filename = str(Path(filename).with_suffix(".mp3"))
        path = Path(filename)
        if not path.exists():
            candidates = [p for p in Path(folder).iterdir() if p.is_file()]
            if not candidates:
                raise FileNotFoundError("Downloader did not create a file.")
            path = max(candidates, key=lambda p: p.stat().st_mtime)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"File is larger than the configured {MAX_FILE_MB} MB limit.")
        return str(path), info.get("title", path.name)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"👋 Welcome to {BOT_NAME}!\n\n"
        "Send a public video link and I’ll try to download it.\n"
        "After sending a link, choose video quality or MP3 audio.\n\n"
        f"👨‍💻 Created by: {CREATOR}\n\n"
        + SUPPORTED_HINT
    )
    await update.message.reply_text(text, disable_web_page_preview=True)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How to use:\n"
        "1. Send a supported public video URL.\n"
        "2. Choose 360p / 720p / 1080p or MP3.\n"
        "3. Save the returned video with Telegram’s Share → Save Video.\n\n"
        "Private/login-only/DRM-protected content is not supported. "
        "Only download content you own or have permission to save.\n\n"
        f"Created by {CREATOR}."
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = safe_url(update.message.text if update.message else "")
    if not url:
        return
    context.user_data["pending_url"] = url
    keyboard = [
        [InlineKeyboardButton("Video 360p", callback_data="dl:360"),
         InlineKeyboardButton("Video 720p", callback_data="dl:720")],
        [InlineKeyboardButton("Video 1080p", callback_data="dl:1080"),
         InlineKeyboardButton("MP3 Audio", callback_data="dl:audio")],
    ]
    await update.message.reply_text(
        "🔗 Link detected. Choose a format:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def download_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get("pending_url")
    if not url:
        await query.edit_message_text("Please send the video link again.")
        return
    mode = query.data.split(":", 1)[1]
    await query.edit_message_text("⏳ Processing your link… this may take a little while.")
    status = await query.message.reply_text("Starting download…")
    folder = tempfile.mkdtemp(prefix="tg-video-")
    try:
        async with semaphore:
            await status.edit_text("⬇️ Downloading and preparing the file…")
            path, title = await asyncio.to_thread(download_media, url, mode, folder)
            size = os.path.getsize(path)
            if size > MAX_FILE_BYTES:
                raise ValueError(f"File exceeds {MAX_FILE_MB} MB.")
            await status.edit_text("📤 Uploading to Telegram…")
            await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
            caption = f"{title[:700]}\n\nCreated by: {CREATOR}"
            with open(path, "rb") as media:
                if mode == "audio":
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id, audio=media,
                        title=title[:64], caption=caption[:1024],
                        read_timeout=120, write_timeout=120, connect_timeout=30
                    )
                elif path.lower().endswith((".mp4", ".m4v", ".mov")):
                    await context.bot.send_video(
                        chat_id=query.message.chat_id, video=media,
                        caption=caption[:1024], supports_streaming=True,
                        read_timeout=120, write_timeout=120, connect_timeout=30
                    )
                else:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id, document=media,
                        caption=caption[:1024],
                        read_timeout=120, write_timeout=120, connect_timeout=30
                    )
            await status.delete()
    except Exception as exc:
        log.warning("Download failed: %s", exc)
        message = str(exc)
        if "Unsupported URL" in message:
            user_msg = "This link/site is not supported by the current downloader."
        elif "Private" in message or "login" in message.lower() or "Sign in" in message:
            user_msg = "This video appears private or requires login. I can only handle accessible public links."
        elif "larger than" in message or "exceeds" in message:
            user_msg = f"The file is over the {MAX_FILE_MB} MB upload limit. Try a lower quality."
        else:
            user_msg = "Sorry, this link could not be downloaded. The site may block access or the link may be unavailable."
        await status.edit_text(f"❌ {user_msg}\n\nTry another public link or a lower quality.")
    finally:
        shutil.rmtree(folder, ignore_errors=True)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin-only command.")
        return
    await update.message.reply_text(
        f"📊 {BOT_NAME}\n"
        f"Creator: {CREATOR}\n"
        f"Process uptime: running\n"
        f"Max file size: {MAX_FILE_MB} MB\n"
        f"Concurrent downloads: {MAX_CONCURRENT}\n"
        f"Admin IDs configured: {len(ADMIN_IDS)}"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin-only command.")
        return
    await update.message.reply_text(
        "Broadcast is intentionally disabled in this starter build because it requires "
        "a database of users and consent-safe subscriber management."
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled bot error", exc_info=context.error)

def main():
    if not TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in your hosting environment.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(download_choice, pattern=r"^dl:(360|720|1080|audio)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_error_handler(error_handler)
    log.info("%s started. Creator: %s", BOT_NAME, CREATOR)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

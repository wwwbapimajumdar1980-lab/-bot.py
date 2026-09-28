import os
import sqlite3
import secrets
import logging
import threading

from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ============================================================
# CONFIG
# ============================================================

# Render Environment Variable থেকে token নেবে
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# তোমার Telegram Admin ID
ADMIN_ID = 1393373043

# SQLite database
DB_NAME = "alpha_apk.db"

# Render automatically PORT দেয়
PORT = int(os.getenv("PORT", "10000"))


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Alpha APK Bot is running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_health_server():
    try:
        server = HTTPServer(
            ("0.0.0.0", PORT),
            HealthHandler
        )

        logger.info("Health server started on port %s", PORT)

        server.serve_forever()

    except Exception as e:
        logger.error(
            "Health server error: %s",
            e,
            exc_info=True
        )


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30
    )

    return conn


def init_db():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            media_type TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT,
            caption TEXT,
            created_at TEXT NOT NULL,
            views INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# ADD MEDIA
# ============================================================

def add_media(
    media_type,
    file_id,
    file_name="",
    caption=""
):

    token = secrets.token_urlsafe(8)

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO media
        (
            token,
            media_type,
            file_id,
            file_name,
            caption,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        token,
        media_type,
        file_id,
        file_name,
        caption,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()

    return token


# ============================================================
# GET MEDIA
# ============================================================

def get_media(token):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            token,
            media_type,
            file_id,
            file_name,
            caption,
            created_at,
            views
        FROM media
        WHERE token = ?
    """, (token,))

    row = cur.fetchone()

    conn.close()

    return row


# ============================================================
# GET ALL MEDIA
# ============================================================

def get_all_media(media_type=None):

    conn = db()
    cur = conn.cursor()

    if media_type:

        cur.execute("""
            SELECT
                id,
                token,
                media_type,
                file_id,
                file_name,
                caption,
                created_at,
                views
            FROM media
            WHERE media_type = ?
            ORDER BY id DESC
        """, (media_type,))

    else:

        cur.execute("""
            SELECT
                id,
                token,
                media_type,
                file_id,
                file_name,
                caption,
                created_at,
                views
            FROM media
            ORDER BY id DESC
        """)

    rows = cur.fetchall()

    conn.close()

    return rows


# ============================================================
# DELETE MEDIA
# ============================================================

def delete_media(media_id):

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM media WHERE id = ?",
        (media_id,)
    )

    conn.commit()
    conn.close()


# ============================================================
# RENAME MEDIA
# ============================================================

def rename_media(
    media_id,
    new_name
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE media
        SET file_name = ?
        WHERE id = ?
    """, (
        new_name,
        media_id
    ))

    conn.commit()
    conn.close()


# ============================================================
# INCREASE VIEWS
# ============================================================

def increase_views(token):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE media
        SET views = views + 1
        WHERE token = ?
    """, (token,))

    conn.commit()
    conn.close()


# ============================================================
# ADMIN CHECK
# ============================================================

def is_admin(user_id):

    return user_id == ADMIN_ID


# ============================================================
# ADMIN KEYBOARD
# ============================================================

def admin_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "➕ Add Media",
                callback_data="admin_add"
            )
        ],

        [
            InlineKeyboardButton(
                "📦 Manage APK",
                callback_data="manage_apk"
            ),

            InlineKeyboardButton(
                "🎬 Manage Video",
                callback_data="manage_video"
            )
        ],

        [
            InlineKeyboardButton(
                "🖼️ Manage Photo",
                callback_data="manage_photo"
            )
        ],

        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="stats"
            )
        ]

    ])


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    args = context.args

    # --------------------------------------------------------
    # DEEP LINK
    # --------------------------------------------------------

    if args:

        token = args[0]

        item = get_media(token)

        if not item:

            await update.message.reply_text(
                "❌ Media link is not available."
            )

            return

        (
            media_id,
            token,
            media_type,
            file_id,
            file_name,
            caption,
            created_at,
            views
        ) = item

        increase_views(token)

        try:

            if media_type == "apk":

                await update.message.reply_document(
                    document=file_id,
                    caption=(
                        caption
                        or f"📦 {file_name or 'APK'}"
                    )
                )

            elif media_type == "video":

                await update.message.reply_video(
                    video=file_id,
                    caption=(
                        caption
                        or f"🎬 {file_name or 'Video'}"
                    )
                )

            elif media_type == "photo":

                await update.message.reply_photo(
                    photo=file_id,
                    caption=(
                        caption
                        or f"🖼️ {file_name or 'Photo'}"
                    )
                )

        except Exception as e:

            logger.error(
                "Sending media failed: %s",
                e,
                exc_info=True
            )

            await update.message.reply_text(
                "❌ Media send failed. "
                "Please contact admin."
            )

        return

    # --------------------------------------------------------
    # NORMAL START
    # --------------------------------------------------------

    keyboard = [

        [
            InlineKeyboardButton(
                "📦 APK",
                callback_data="user_apk"
            ),

            InlineKeyboardButton(
                "🎬 Video",
                callback_data="user_video"
            )
        ],

        [
            InlineKeyboardButton(
                "🖼️ Photo",
                callback_data="user_photo"
            )
        ]

    ]

    await update.message.reply_text(

        "👋 Welcome to Alpha APK Bot!\n\n"
        "Select a category below to browse "
        "available media.",

        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# ADMIN PANEL
# ============================================================

async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ Access denied."
        )

        return

    # Clear previous states
    context.user_data.pop(
        "adding_media",
        None
    )

    context.user_data.pop(
        "rename_media_id",
        None
    )

    await update.message.reply_text(
        "🔐 Alpha APK — Admin Control Center\n\n"
        "Choose an option below:",
        reply_markup=admin_keyboard()
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    data = query.data

    user_id = query.from_user.id

    # ========================================================
    # ADMIN CALLBACK PROTECTION
    # ========================================================

    admin_callbacks = (
        "admin_",
        "manage_",
        "media_",
        "rename_",
        "link_",
        "delete_",
        "confirm_delete_",
        "back_",
        "stats"
    )

    if data.startswith(admin_callbacks):

        if not is_admin(user_id):

            await query.answer(
                "Access denied.",
                show_alert=True
            )

            return

    await query.answer()

    # ========================================================
    # ADD MEDIA
    # ========================================================

    if data == "admin_add":

        context.user_data["adding_media"] = True

        keyboard = [[
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel_add"
            )
        ]]

        await query.edit_message_text(

            "➕ Add Media Mode\n\n"

            "Send one of the following:\n\n"
            "📦 APK → Send as Document\n"
            "🎬 Video → Send as Video\n"
            "🖼️ Photo → Send as Photo\n\n"

            "The bot will automatically save the "
            "Telegram file_id and create a unique "
            "download link.",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # ========================================================
    # CANCEL ADD
    # ========================================================

    if data == "cancel_add":

        context.user_data["adding_media"] = False

        await query.edit_message_text(
            "❌ Add Media cancelled.",
            reply_markup=admin_keyboard()
        )

        return

    # ========================================================
    # MANAGE LIST
    # ========================================================

    if data in (
        "manage_apk",
        "manage_video",
        "manage_photo"
    ):

        media_type = data.replace(
            "manage_",
            ""
        )

        rows = get_all_media(
            media_type
        )

        if not rows:

            await query.edit_message_text(

                f"📭 No {media_type.upper()} "
                "found.",

                reply_markup=InlineKeyboardMarkup([

                    [
                        InlineKeyboardButton(
                            "⬅️ Admin Panel",
                            callback_data="back_admin"
                        )
                    ]

                ])
            )

            return

        keyboard = []

        for row in rows:

            media_id = row[0]

            name = (
                row[4]
                or f"{media_type.upper()} #{media_id}"
            )

            if len(name) > 30:

                name = name[:27] + "..."

            keyboard.append([

                InlineKeyboardButton(
                    f"📄 {name}",
                    callback_data=f"media_{media_id}"
                )

            ])

        keyboard.append([

            InlineKeyboardButton(
                "⬅️ Admin Panel",
                callback_data="back_admin"
            )

        ])

        await query.edit_message_text(

            f"📁 Manage {media_type.upper()}\n\n"
            f"Total: {len(rows)}",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # ========================================================
    # MEDIA DETAILS
    # ========================================================

    if data.startswith("media_"):

        media_id = int(
            data.split("_")[1]
        )

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                token,
                media_type,
                file_id,
                file_name,
                caption,
                created_at,
                views
            FROM media
            WHERE id = ?
        """, (media_id,))

        row = cur.fetchone()

        conn.close()

        if not row:

            await query.edit_message_text(
                "❌ Media not found."
            )

            return

        (
            media_id,
            token,
            media_type,
            file_id,
            file_name,
            caption,
            created_at,
            views
        ) = row

        bot_username = context.bot.username

        link = (
            f"https://t.me/"
            f"{bot_username}"
            f"?start={token}"
        )

        keyboard = [

            [
                InlineKeyboardButton(
                    "✏️ Rename",
                    callback_data=f"rename_{media_id}"
                )
            ],

            [
                InlineKeyboardButton(
                    "🔗 Get Link",
                    callback_data=f"link_{media_id}"
                )
            ],

            [
                InlineKeyboardButton(
                    "🗑️ Delete",
                    callback_data=f"delete_{media_id}"
                )
            ],

            [
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data=f"back_{media_type}"
                )
            ]

        ]

        await query.edit_message_text(

            "📄 Media Details\n\n"

            f"🆔 ID: `{media_id}`\n"
            f"📁 Type: `{media_type}`\n"
            f"📝 Name: `{file_name or 'Not set'}`\n"
            f"👁️ Requests: `{views}`\n"
            f"📅 Added: `{created_at}`\n\n"

            "🔗 Link:\n"
            f"`{link}`",

            parse_mode="Markdown",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # ========================================================
    # GET LINK
    # ========================================================

    if data.startswith("link_"):

        media_id = int(
            data.split("_")[1]
        )

        conn = db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT token, file_name
            FROM media
            WHERE id = ?
            """,
            (media_id,)
        )

        row = cur.fetchone()

        conn.close()

        if not row:

            await query.message.reply_text(
                "❌ Media not found."
            )

            return

        token, file_name = row

        bot_username = context.bot.username

        link = (
            f"https://t.me/"
            f"{bot_username}"
            f"?start={token}"
        )

        await query.message.reply_text(

            "🔗 Media Link\n\n"

            f"📄 {file_name or 'Media'}\n\n"

            f"{link}\n\n"

            "Share this link with users.",

            parse_mode="Markdown"
        )

        return

    # ========================================================
    # DELETE
    # ========================================================

    if data.startswith("delete_"):

        media_id = int(
            data.split("_")[1]
        )

        keyboard = [

            [
                InlineKeyboardButton(
                    "✅ Yes, Delete",
                    callback_data=(
                        f"confirm_delete_{media_id}"
                    )
                )
            ],

            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=f"media_{media_id}"
                )
            ]

        ]

        await query.edit_message_text(

            "⚠️ Are you sure you want to "
            "delete this media?",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # ========================================================
    # CONFIRM DELETE
    # ========================================================

    if data.startswith("confirm_delete_"):

        media_id = int(
            data.split("_")[2]
        )

        delete_media(media_id)

        await query.edit_message_text(

            "✅ Media successfully deleted.",

            reply_markup=admin_keyboard()
        )

        return

    # ========================================================
    # RENAME
    # ========================================================

    if data.startswith("rename_"):

        media_id = int(
            data.split("_")[1]
        )

        context.user_data[
            "rename_media_id"
        ] = media_id

        await query.edit_message_text(

            "✏️ Rename Media\n\n"

            "Send the new name now.\n\n"

            "Example:\n"
            "`CapCut Premium APK`",

            parse_mode="Markdown"
        )

        return

    # ========================================================
    # BACK ADMIN
    # ========================================================

    if data == "back_admin":

        context.user_data.pop(
            "adding_media",
            None
        )

        context.user_data.pop(
            "rename_media_id",
            None
        )

        await query.edit_message_text(

            "🔐 Alpha APK — Admin Panel\n\n"
            "Choose an option below:",

            reply_markup=admin_keyboard()
        )

        return

    # ========================================================
    # BACK MEDIA LIST
    # ========================================================

    if data.startswith("back_"):

        media_type = data.replace(
            "back_",
            ""
        )

        rows = get_all_media(
            media_type
        )

        keyboard = []

        for row in rows:

            media_id = row[0]

            name = (
                row[4]
                or f"{media_type.upper()} #{media_id}"
            )

            keyboard.append([

                InlineKeyboardButton(
                    f"📄 {name[:30]}",
                    callback_data=f"media_{media_id}"
                )

            ])

        keyboard.append([

            InlineKeyboardButton(
                "⬅️ Admin Panel",
                callback_data="back_admin"
            )

        ])

        await query.edit_message_text(

            f"📁 Manage {media_type.upper()}",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # ========================================================
    # USER CATEGORY
    # ========================================================

    if data.startswith("user_"):

        media_type = data.replace(
            "user_",
            ""
        )

        rows = get_all_media(
            media_type
        )

        if not rows:

            await query.edit_message_text(

                "📭 No media available "
                "in this category.",

            )

            return

        keyboard = []

        for row in rows:

            media_id = row[0]

            token = row[1]

            name = (
                row[4]
                or f"{media_type.upper()} #{media_id}"
            )

            link = (
                f"https://t.me/"
                f"{context.bot.username}"
                f"?start={token}"
            )

            keyboard.append([

                InlineKeyboardButton(
                    f"📄 {name[:25]}",
                    url=link
                )

            ])

        keyboard.append([

            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="user_back"
            )

        ])

        await query.edit_message_text(

            f"📁 Available {media_type.upper()}",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # ========================================================
    # USER BACK
    # ========================================================

    if data == "user_back":

        keyboard = [

            [
                InlineKeyboardButton(
                    "📦 APK",
                    callback_data="user_apk"
                ),

                InlineKeyboardButton(
                    "🎬 Video",
                    callback_data="user_video"
                )
            ],

            [
                InlineKeyboardButton(
                    "🖼️ Photo",
                    callback_data="user_photo"
                )
            ]

        ]

        await query.edit_message_text(

            "👋 Select a category:",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # ========================================================
    # STATISTICS
    # ========================================================

    if data == "stats":

        all_rows = get_all_media()

        apk = sum(
            1 for x in all_rows
            if x[2] == "apk"
        )

        video = sum(
            1 for x in all_rows
            if x[2] == "video"
        )

        photo = sum(
            1 for x in all_rows
            if x[2] == "photo"
        )

        total_views = sum(
            x[7] for x in all_rows
        )

        await query.edit_message_text(

            "📊 Alpha APK Statistics\n\n"

            f"📦 APK: `{apk}`\n"
            f"🎬 Video: `{video}`\n"
            f"🖼️ Photo: `{photo}`\n"
            f"📁 Total Media: `{len(all_rows)}`\n"
            f"👁️ Total Requests: `{total_views}`",

            parse_mode="Markdown",

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="back_admin"
                    )
                ]

            ])
        )

        return


# ============================================================
# MEDIA UPLOAD HANDLER
# ============================================================

async def media_upload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        return

    if not context.user_data.get(
        "adding_media"
    ):

        return

    media_type = None
    file_id = None
    file_name = ""

    # --------------------------------------------------------
    # DOCUMENT / APK
    # --------------------------------------------------------

    if update.message.document:

        document = update.message.document

        file_id = document.file_id

        file_name = (
            document.file_name
            or "APK"
        )

        media_type = "apk"

    # --------------------------------------------------------
    # VIDEO
    # --------------------------------------------------------

    elif update.message.video:

        video = update.message.video

        file_id = video.file_id

        file_name = "Video"

        media_type = "video"

    # --------------------------------------------------------
    # PHOTO
    # --------------------------------------------------------

    elif update.message.photo:

        photo = update.message.photo[-1]

        file_id = photo.file_id

        file_name = "Photo"

        media_type = "photo"

    else:

        await update.message.reply_text(

            "❌ Please send an APK/document, "
            "video or photo."

        )

        return

    caption = (
        update.message.caption
        or ""
    )

    try:

        token = add_media(

            media_type,
            file_id,
            file_name,
            caption

        )

    except sqlite3.IntegrityError:

        await update.message.reply_text(
            "❌ Could not save media. "
            "Please try again."
        )

        return

    context.user_data[
        "adding_media"
    ] = False

    link = (
        f"https://t.me/"
        f"{context.bot.username}"
        f"?start={token}"
    )

    await update.message.reply_text(

        "✅ Media Successfully Added!\n\n"

        f"📁 Type: `{media_type}`\n"
        f"📝 Name: `{file_name}`\n"
        f"🔑 Token: `{token}`\n\n"

        "🔗 Your Link:\n"
        f"`{link}`\n\n"

        "Share this link with users.",

        parse_mode="Markdown"
    )


# ============================================================
# RENAME MESSAGE
# ============================================================

async def rename_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        return

    media_id = context.user_data.get(
        "rename_media_id"
    )

    if not media_id:

        return

    if not update.message.text:

        return

    new_name = (
        update.message.text.strip()
    )

    if not new_name:

        return

    rename_media(
        media_id,
        new_name
    )

    context.user_data.pop(
        "rename_media_id",
        None
    )

    await update.message.reply_text(

        "✅ Name changed successfully!\n\n"
        f"📝 New Name: {new_name}"

    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context
):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # TOKEN CHECK
    # --------------------------------------------------------

    if not BOT_TOKEN:

        logger.error(
            "BOT_TOKEN environment variable is missing!"
        )

        print(
            "\n❌ BOT_TOKEN is missing!\n"
            "Set BOT_TOKEN in Render Environment Variables.\n"
        )

        return

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    init_db()

    # --------------------------------------------------------
    # START HEALTH SERVER
    # --------------------------------------------------------

    health_thread = threading.Thread(
        target=run_health_server,
        daemon=True
    )

    health_thread.start()

    # --------------------------------------------------------
    # TELEGRAM APPLICATION
    # --------------------------------------------------------

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "777",
            admin_panel
        )
    )

    # --------------------------------------------------------
    # CALLBACK BUTTONS
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # --------------------------------------------------------
    # MEDIA UPLOAD
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            (
                filters.Document.ALL
                | filters.VIDEO
                | filters.PHOTO
            ),
            media_upload
        )
    )

    # --------------------------------------------------------
    # TEXT / RENAME
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            rename_handler
        )
    )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    print("====================================")
    print(" Alpha APK Bot Started")
    print(" Admin Command: /777")
    print(" Database:", DB_NAME)
    print(" Health Port:", PORT)
    print("====================================")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()

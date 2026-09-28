import os
import sqlite3
import secrets
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_NEW_BOT_TOKEN_HERE")

# তোমার Admin Chat ID
ADMIN_ID = 1393373043

DB_NAME = "alpha_apk.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_NAME)


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


def add_media(media_type, file_id, file_name="", caption=""):
    token = secrets.token_urlsafe(8)

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO media
        (token, media_type, file_id, file_name, caption, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        token,
        media_type,
        file_id,
        file_name,
        caption,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return token


def get_media(token):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, token, media_type, file_id, file_name,
               caption, created_at, views
        FROM media
        WHERE token = ?
    """, (token,))

    row = cur.fetchone()

    conn.close()

    return row


def get_all_media(media_type=None):
    conn = db()
    cur = conn.cursor()

    if media_type:
        cur.execute("""
            SELECT id, token, media_type, file_id,
                   file_name, caption, created_at, views
            FROM media
            WHERE media_type = ?
            ORDER BY id DESC
        """, (media_type,))
    else:
        cur.execute("""
            SELECT id, token, media_type, file_id,
                   file_name, caption, created_at, views
            FROM media
            ORDER BY id DESC
        """)

    rows = cur.fetchall()
    conn.close()

    return rows


def delete_media(media_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM media WHERE id = ?",
        (media_id,)
    )

    conn.commit()
    conn.close()


def rename_media(media_id, new_name):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE media
        SET file_name = ?
        WHERE id = ?
    """, (new_name, media_id))

    conn.commit()
    conn.close()


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
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
                "❌ এই media link আর available নেই।"
            )
            return

        media_id, token, media_type, file_id, file_name, caption, created_at, views = item

        increase_views(token)

        try:

            if media_type == "apk":

                await update.message.reply_document(
                    document=file_id,
                    caption=caption or f"📦 {file_name or 'APK'}"
                )

            elif media_type == "video":

                await update.message.reply_video(
                    video=file_id,
                    caption=caption or f"🎬 {file_name or 'Video'}"
                )

            elif media_type == "photo":

                await update.message.reply_photo(
                    photo=file_id,
                    caption=caption or f"🖼️ {file_name or 'Photo'}"
                )

        except Exception as e:

            logger.error("Sending media failed: %s", e)

            await update.message.reply_text(
                "❌ Media পাঠানো যায়নি। পরে আবার চেষ্টা করুন।"
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
                "🎥 Video",
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
        "তোমার কাছে কোনো media link থাকলে সেটাতে click করলেই "
        "আমি automatically সেই file পাঠিয়ে দেব।",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# ADMIN PANEL
# ============================================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "❌ Access denied."
        )
        return

    keyboard = [

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
                "🎥 Manage Video",
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

    ]

    await update.message.reply_text(
        "🔐 **Alpha APK — Admin Control Center**\n\n"
        "নিচের menu থেকে control করো:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    data = query.data

    # ========================================================
    # ADMIN
    # ========================================================

    if data.startswith("admin_") or \
       data.startswith("manage_") or \
       data.startswith("media_") or \
       data in ["stats", "back_admin"]:

        if not is_admin(user_id):

            await query.answer(
                "Access denied",
                show_alert=True
            )

            return

    # ========================================================
    # ADD MEDIA
    # ========================================================

    if data == "admin_add":

        context.user_data["adding_media"] = True

        keyboard = [
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="cancel_add"
                )
            ]
        ]

        await query.edit_message_text(
            "➕ **Add Media Mode**\n\n"
            "এখন আমাকে APK / Video / Photo পাঠাও।\n\n"
            "📦 APK → Document হিসেবে পাঠাও\n"
            "🎥 Video → Video হিসেবে পাঠাও\n"
            "🖼️ Photo → Photo হিসেবে পাঠাও\n\n"
            "File পাওয়ার পর আমি automatically database-এ save "
            "করব এবং unique link দেব।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # CANCEL ADD
    # ========================================================

    if data == "cancel_add":

        context.user_data["adding_media"] = False

        await query.edit_message_text(
            "❌ Add Media cancelled."
        )

        return

    # ========================================================
    # MANAGE LIST
    # ========================================================

    if data in ["manage_apk", "manage_video", "manage_photo"]:

        media_type = data.replace("manage_", "")

        rows = get_all_media(media_type)

        if not rows:

            await query.edit_message_text(
                f"📭 কোনো {media_type.upper()} পাওয়া যায়নি।"
            )

            return

        keyboard = []

        for row in rows:

            media_id = row[0]
            name = row[4] or f"{media_type.upper()} #{media_id}"

            if len(name) > 30:
                name = name[:27] + "..."

            keyboard.append([
                InlineKeyboardButton(
                    f"📁 {name}",
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
            f"📂 **Manage {media_type.upper()}**\n\n"
            f"Total: {len(rows)}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # MEDIA DETAILS
    # ========================================================

    if data.startswith("media_"):

        media_id = int(data.split("_")[1])

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, token, media_type, file_id,
                   file_name, caption, created_at, views
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

        media_id, token, media_type, file_id, file_name, caption, created_at, views = row

        bot_username = context.bot.username

        link = f"https://t.me/{bot_username}?start={token}"

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
            f"📁 **Media Details**\n\n"
            f"🆔 ID: `{media_id}`\n"
            f"📂 Type: `{media_type}`\n"
            f"📛 Name: `{file_name or 'Not set'}`\n"
            f"👁️ Requests: `{views}`\n"
            f"📅 Added: `{created_at}`\n\n"
            f"🔗 Link:\n`{link}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # GET LINK
    # ========================================================

    if data.startswith("link_"):

        media_id = int(data.split("_")[1])

        conn = db()
        cur = conn.cursor()

        cur.execute(
            "SELECT token, file_name FROM media WHERE id = ?",
            (media_id,)
        )

        row = cur.fetchone()

        conn.close()

        if not row:
            return

        token, file_name = row

        bot_username = context.bot.username

        link = f"https://t.me/{bot_username}?start={token}"

        await query.message.reply_text(
            f"🔗 **Media Link**\n\n"
            f"📛 {file_name or 'Media'}\n\n"
            f"{link}\n\n"
            f"এই link যেকোনো জায়গায় share করতে পারো।",
            parse_mode="Markdown"
        )

        return

    # ========================================================
    # DELETE
    # ========================================================

    if data.startswith("delete_"):

        media_id = int(data.split("_")[1])

        keyboard = [

            [
                InlineKeyboardButton(
                    "✅ Yes, Delete",
                    callback_data=f"confirm_delete_{media_id}"
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
            "⚠️ তুমি কি সত্যিই এই media delete করতে চাও?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # CONFIRM DELETE
    # ========================================================

    if data.startswith("confirm_delete_"):

        media_id = int(data.split("_")[2])

        delete_media(media_id)

        await query.edit_message_text(
            "✅ Media successfully deleted."
        )

        return

    # ========================================================
    # RENAME
    # ========================================================

    if data.startswith("rename_"):

        media_id = int(data.split("_")[1])

        context.user_data["rename_media_id"] = media_id

        await query.edit_message_text(
            "✏️ নতুন নাম পাঠাও।\n\n"
            "Example:\n"
            "`CapCut Premium APK`",
            parse_mode="Markdown"
        )

        return

    # ========================================================
    # BACK ADMIN
    # ========================================================

    if data == "back_admin":

        keyboard = [

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
                    "🎥 Manage Video",
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

        ]

        await query.edit_message_text(
            "🔐 **Alpha APK — Admin Panel**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # BACK MEDIA LIST
    # ========================================================

    if data.startswith("back_"):

        media_type = data.replace("back_", "")

        rows = get_all_media(media_type)

        keyboard = []

        for row in rows:

            media_id = row[0]

            name = row[4] or f"{media_type.upper()} #{media_id}"

            keyboard.append([
                InlineKeyboardButton(
                    f"📁 {name[:30]}",
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
            f"📂 Manage {media_type.upper()}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # USER CATEGORY
    # ========================================================

    if data.startswith("user_"):

        media_type = data.replace("user_", "")

        rows = get_all_media(media_type)

        if not rows:

            await query.edit_message_text(
                "📭 এই category-তে এখন কোনো media নেই।"
            )

            return

        keyboard = []

        for row in rows:

            media_id = row[0]
            token = row[1]
            name = row[4] or f"{media_type.upper()} #{media_id}"

            link = f"https://t.me/{context.bot.username}?start={token}"

            keyboard.append([
                InlineKeyboardButton(
                    f"📁 {name[:25]}",
                    url=link
                )
            ])

        await query.edit_message_text(
            f"📂 Available {media_type.upper()}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # STATISTICS
    # ========================================================

    if data == "stats":

        all_rows = get_all_media()

        apk = len([x for x in all_rows if x[2] == "apk"])
        video = len([x for x in all_rows if x[2] == "video"])
        photo = len([x for x in all_rows if x[2] == "photo"])

        total_views = sum(x[7] for x in all_rows)

        await query.edit_message_text(
            "📊 **Alpha APK Statistics**\n\n"
            f"📦 APK: `{apk}`\n"
            f"🎥 Video: `{video}`\n"
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

async def media_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    if not context.user_data.get("adding_media"):
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

        file_name = document.file_name or "APK"

        # APK detection
        if file_name.lower().endswith(".apk"):

            media_type = "apk"

        else:

            # Document হলেও APK হিসেবে save করা যাবে
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
            "❌ Please APK, Video অথবা Photo পাঠাও।"
        )

        return

    caption = update.message.caption or ""

    token = add_media(
        media_type,
        file_id,
        file_name,
        caption
    )

    context.user_data["adding_media"] = False

    link = f"https://t.me/{context.bot.username}?start={token}"

    await update.message.reply_text(
        "✅ **Media Successfully Added!**\n\n"
        f"📂 Type: `{media_type}`\n"
        f"📛 Name: `{file_name}`\n"
        f"🆔 Token: `{token}`\n\n"
        f"🔗 **Your Link:**\n"
        f"`{link}`\n\n"
        "এই link share করলে user bot-এ আসবে এবং "
        "automatically এই media পেয়ে যাবে।",
        parse_mode="Markdown"
    )


# ============================================================
# RENAME MESSAGE
# ============================================================

async def rename_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    media_id = context.user_data.get("rename_media_id")

    if not media_id:
        return

    new_name = update.message.text.strip()

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
        f"✅ Name changed successfully!\n\n"
        f"📛 New Name: {new_name}"
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update, context):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN or BOT_TOKEN == "PASTE_NEW_BOT_TOKEN_HERE":

        print(
            "\n❌ BOT_TOKEN পাওয়া যায়নি!\n"
            "প্রথমে environment variable set করো:\n\n"
            'export BOT_TOKEN="YOUR_NEW_BOT_TOKEN"\n'
        )

        return

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("777", admin_panel)
    )

    # Callback buttons
    application.add_handler(
        CallbackQueryHandler(callback_handler)
    )

    # Rename text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            rename_handler
        )
    )

    # Media uploads
    application.add_handler(
        MessageHandler(
            filters.Document.ALL |
            filters.VIDEO |
            filters.PHOTO,
            media_upload
        )
    )

    application.add_error_handler(
        error_handler
    )

    print("====================================")
    print(" Alpha APK Bot Started")
    print(" Admin Command: /777")
    print(" Database:", DB_NAME)
    print("====================================")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()

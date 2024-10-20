import asyncio
import html
import json
import logging
from dataclasses import dataclass

import uvicorn

from dj_server.asgi import application
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest

from telegram.constants import ParseMode
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    )
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ContextTypes,
    ExtBot,
    CallbackQueryHandler,
    ConversationHandler
)

import dj_server.config as CONFIG

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

top_states = {
    "CHOOSE_CATEGORY": 0,
    "CATEGORY_CARDS": 1
}

category_cards_states = {
    "PREVIOUS": 0,
    "NEXT": 1,
    "ADD": 2,
    "ENTER_COUNT": 3,
    "REMOVE": 4,
    "INTO_CART": 5,
    "BACK": 6
}

@dataclass
class WebhookUpdate:
    """Simple dataclass to wrap a custom update type"""

    user_id: int
    payload: str


class CustomContext(CallbackContext[ExtBot, dict, dict, dict]):
    """
    Custom CallbackContext class that makes `user_data` available for updates of type
    `WebhookUpdate`.
    """

    @classmethod
    def from_update(
        cls,
        update: object,
        application: "Application",
    ) -> "CustomContext":
        if isinstance(update, WebhookUpdate):
            return cls(application=application, user_id=update.user_id)
        return super().from_update(update, application)


async def start(update: Update, context: CustomContext) -> None:
    """Display start message"""

    text = CONFIG.START_TEXT
    keyboard = [
        [
            InlineKeyboardButton("🛍 перейти в каталог", callback_data=top_states["CHOOSE_CATEGORY"]),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(
        photo=f"{CONFIG.URL}/static/img/bot/logo.jpg",
        caption=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

    return top_states["CHOOSE_CATEGORY"]


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display a message to the user to select a product category"""

    query = update.callback_query

    await query.answer()

    text = CONFIG.CHOOSE_CATEGORY_TEXT
    keyboard = [
        [InlineKeyboardButton(button_name, callback_data=button_item)] 
            for button_item, button_name in CONFIG.CATEGORY_CHOICES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_media(
        media=InputMediaPhoto(
            media=f"{CONFIG.URL}/static/img/bot/in_catalog.jpg",
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
        ),
        reply_markup=reply_markup
    )

    return top_states["CATEGORY_CARDS"]


async def category_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all products in this category as cards"""
    
    query = update.callback_query

    await query.answer()

    text = CONFIG.CATEGORY_CARDS_TEXT(query.data)
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=category_cards_states["PREVIOUS"]),
            InlineKeyboardButton("➡️", callback_data=category_cards_states["NEXT"]),
        ],
        [
            InlineKeyboardButton("➕", callback_data=category_cards_states["ADD"]),
            InlineKeyboardButton("ввести кол-во", callback_data=category_cards_states["ENTER_COUNT"]),
            InlineKeyboardButton("➖", callback_data=category_cards_states["REMOVE"]),
        ],
        [
            InlineKeyboardButton("🛒в корзину", callback_data=category_cards_states["INTO_CART"])
        ],
        [
            InlineKeyboardButton("🔙назад", callback_data=category_cards_states["BACK"])
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_media(
        media=InputMediaPhoto(
            media=f"{CONFIG.URL}/static/img/categories/{query.data}.jpg",
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
        )
    )


async def change_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change product card"""

    query = update.callback_query

    await query.answer()
    
    match 


async def cart(update: Update, context: ContextTypes.DEFAULT_TYPE):



async def webhook_update(update: WebhookUpdate, context: CustomContext) -> None:
    """Handle custom updates."""
    chat_member = await context.bot.get_chat_member(chat_id=update.user_id, user_id=update.user_id)
    payloads = context.user_data.setdefault("payloads", [])
    payloads.append(update.payload)
    combined_payloads = "</code>\n• <code>".join(payloads)
    text = (
        f"The user {chat_member.user.mention_html()} has sent a new payload. "
        f"So far they have sent the following payloads: \n\n• <code>{combined_payloads}</code>"
    )
    await context.bot.send_message(chat_id=CONFIG.ADMIN_CHAT_ID, text=text, parse_mode=ParseMode.HTML)


async def custom_updates(request: HttpRequest) -> HttpResponse:
    """Handle incoming webhook updates"""

    try:
        user_id = int(request.GET["user_id"])
        payload = request.GET["payload"]
    except KeyError:
        return HttpResponseBadRequest(
            "Please pass both `user_id` and `payload` as query parameters.",
        )
    except ValueError:
        return HttpResponseBadRequest("The `user_id` must be a string!")

    await ptb_application.update_queue.put(WebhookUpdate(user_id=user_id, payload=payload))
    return HttpResponse()


# Set up PTB application and a web application for handling the incoming requests.
context_types = ContextTypes(context=CustomContext)
ptb_application = (
    Application.builder().token(CONFIG.TOKEN).updater(None).context_types(context_types).build()
)


# Register handlers
ptb_application.add_handler(
    ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            top_states["CHOOSE_CATEGORY"]: [CallbackQueryHandler(choose_category)],
            top_states["CATEGORY_CARDS"]: [CallbackQueryHandler(category_cards)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )
)


async def main() -> None:
    """Finalize configuration and run the applications."""

    webserver = uvicorn.Server(
        config=uvicorn.Config(
            app=application,
            port=CONFIG.PORT,
            use_colors=False,
            host="127.0.0.1",
        )
    )

    # Pass webhook settings to telegram
    await ptb_application.bot.set_webhook(url=f"{CONFIG.URL}/telegram", allowed_updates=Update.ALL_TYPES)

    # Run application and webserver together
    async with ptb_application:
        await ptb_application.start()
        await webserver.serve()
        await ptb_application.stop()
        

if __name__ == "__main__":
    asyncio.run(main())
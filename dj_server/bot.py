import asyncio
import logging
from dataclasses import dataclass

import uvicorn
from dj_server.asgi import application

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.db.models import Q
from asgiref.sync import sync_to_async

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

import app_bot.models as models
import dj_server.config as CONFIG

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

SPLIT = "_"

top_states = {
    "START": 0,
    "ADMIN_PANEL": 1,
    "CHOOSE_CATEGORY": 2,
    "CATEGORY_CARDS": 3,
    "PRODUCT_CARDS": 4,
    "INTO_CART": 5,
    "CONFIRMED_ORDER_LIST": 6,
    "COMPLETED_ORDER_LIST": 7
}
product_card_states = {
    "PREVIOUS": 1_0,
    "NEXT": 1_1,
    "ADD": 1_2,
    "ENTER_COUNT": 1_3,
    "REMOVE": 1_4,
}
admin_panel_states = {

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


async def create_order():
    pass

async def remove_order():
    pass

async def add_part_to_order():
    pass

async def remove_part_from_order():
    pass


async def start(update: Update, context: CustomContext):
    """Display start message"""

    user_id = update.effective_chat.id

    if await (models.Admin.objects.filter(admin_id=user_id)).aexists():
        return top_states["ADMIN_PANEL"]
    
    user, _ = await models.User.objects.aget_or_create(user_id=user_id)
    order, _ = await models.Order.objects.aget_or_create(user_id=user)

    text = CONFIG.START_TEXT
    keyboard = [
        [
            InlineKeyboardButton("🛍 перейти в каталог", callback_data=top_states["CHOOSE_CATEGORY"]),
        ],
        [
            InlineKeyboardButton("🕓 выполняемые заказы", callback_data=top_states["CONFIRMED_ORDER_LIST"])
        ],
        [
            InlineKeyboardButton("✅ завершенные заказы", callback_data=top_states["COMPLETED_ORDER_LIST"])
        ]
    ]

    if bool(order.parts):
        text += CONFIG.START_TEXT_PARTS_IN_CART
        keyboard.append(
            [InlineKeyboardButton("🛒 корзина", callback_data=top_states["INTO_CART"])]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query

    if bool(query):
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{CONFIG.URL}/static/img/bot/logo.jpg",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_photo(
            photo=f"{CONFIG.URL}/static/img/bot/logo.jpg",
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    return top_states["START"]


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #TODO realize
    pass


async def confirmed_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #TODO realize
    pass


async def completed_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #TODO realize
    pass


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display a message to the user to select a product category"""

    query = update.callback_query

    text = CONFIG.CHOOSE_CATEGORY_TEXT
    keyboard = [
        [InlineKeyboardButton("↩️назад", callback_data=str(top_states["START"]))]
    ]
    keyboard += [
        [InlineKeyboardButton(button_name, callback_data=str(top_states["CATEGORY_CARDS"]) + SPLIT + category)] 
            for category, button_name in CONFIG.CATEGORY_CHOICES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.answer()
    await query.edit_message_media(
        media=InputMediaPhoto(
            media=f"{CONFIG.URL}/static/img/bot/in_catalog.jpg",
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
        ),
        reply_markup=reply_markup
    )

    return top_states["CHOOSE_CATEGORY"]


async def category_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all products in this category"""
    
    query = update.callback_query
    category = query.data.split(SPLIT)[1]

    parts = models.Part.objects.filter(category=category)

    text = (
        f"*[{CONFIG.CATEGORY_CHOICES[category]}]*\n"
        f"\n\n"
    )

    keyboard = [
        [InlineKeyboardButton("↩️назад", callback_data=str(top_states["CHOOSE_CATEGORY"]))]
    ]

    if await sync_to_async(bool)(parts) == True:
        text += (
            f"В наличии:\n\n"
        )

        keyboard.insert(0, [InlineKeyboardButton("➡️", callback_data=str(top_states["PRODUCT_CARDS"]) + SPLIT + category)])

        async for part in parts:
            text += f" ●  *{part.name}*, {part.available_count}шт.\n"

    else:
        text += (
            f"Пока здесь пусто.."
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.answer()
    await query.edit_message_media(
        media=InputMediaPhoto(
            media=f"{CONFIG.URL}/static/img/categories/{category}.jpg",
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
        ),
        reply_markup=reply_markup
    )

    return top_states["CATEGORY_CARDS"]


async def product_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all info about chosen product in this category"""

    #TODO: realize functional

    query = update.callback_query
    callback, category = query.data.split(SPLIT, 1)

    text = (
        f"*[{CONFIG.CATEGORY_CHOICES[part.category]}]*\n"
        f"\n\n"
        f"*{part.name}*\n"
        f"_{part.description}_\n\n"
        f"в наличии: *{part.available_count} шт.*"
    )

    if callback == str(top_states["PRODUCT_CARDS"]):
        part = await models.Part.objects.filter(category=category).afirst()

    if callback == str(product_card_states["PREVIOUS"]):
        category, part_id = category.split(SPLIT)
        part = await models.Part.objects.filter(Q(category=category) & Q(part_id__lt=part_id)).alast()

    if callback == str(product_card_states["NEXT"]):
        category, part_id = category.split(SPLIT)
        part = await models.Part.objects.filter(Q(category=category) & Q(part_id__gt=part_id)).afirst()

    if callback == str(product_card_states["REMOVE"]):
        pass

    if callback == str(product_card_states["ADD"]):
        pass

    if callback == str(product_card_states["ENTER_COUNT"]):
        pass

    if callback == str(product_card_states["INTO_CART"]):
        pass

    # if callback == str("0"):
    #     pass

    img = part.image

    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=str(product_card_states["PREVIOUS"]) + SPLIT + category + SPLIT + str(part.part_id)),
            InlineKeyboardButton("➡️", callback_data=str(product_card_states["NEXT"]) + SPLIT + category + SPLIT + str(part.part_id)),
        ],
        [
            InlineKeyboardButton("➕", callback_data=str(product_card_states["ADD"])),
            InlineKeyboardButton("ввести кол-во", callback_data=str(product_card_states["ENTER_COUNT"])),
            InlineKeyboardButton("➖", callback_data=str(product_card_states["REMOVE"])),
        ],
        [
            InlineKeyboardButton("🛒в корзину", callback_data=str(top_states["INTO_CART"]))
        ],
        [
            InlineKeyboardButton("↩️назад", callback_data=str(top_states["CHOOSE_CATEGORY"]))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.answer()
    await query.edit_message_media(
        media=InputMediaPhoto(
            media=img,
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
        ),
        reply_markup=reply_markup
    )

    return top_states["PRODUCT_CARDS"]


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
            top_states["START"]: [
                CallbackQueryHandler(
                    choose_category, 
                    pattern="^" + str(top_states["CHOOSE_CATEGORY"]) + "$"
                ),
            ],
            top_states["CHOOSE_CATEGORY"]: [
                CallbackQueryHandler(
                    start, 
                    pattern="^" + str(top_states["START"]) + "$"
                ),
                CallbackQueryHandler(
                    category_cards,
                    pattern="^" + str(top_states["CATEGORY_CARDS"]) + "_[A-Z]{1,8}$"
                )
            ],
            top_states["CATEGORY_CARDS"]: [
                CallbackQueryHandler(
                    choose_category, 
                    pattern="^" + str(top_states["CHOOSE_CATEGORY"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(top_states["PRODUCT_CARDS"]) + "_[A-Z]{1,8}$"
                ),
            ],
            top_states["PRODUCT_CARDS"]: [
                CallbackQueryHandler(
                    choose_category, 
                    pattern="^" + str(top_states["CHOOSE_CATEGORY"]) + "_[A-Z]{1,8}$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(top_states["PRODUCT_CARDS"]) + "_[A-Z]{1,8}_[0-9]{1,8}$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(product_card_states["NEXT"]) + "_[A-Z]{1,8}_[0-9]{1,8}$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(product_card_states["PREVIOUS"]) + "_[A-Z]{1,8}_[0-9]{1,8}$"
                ),
            ]
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
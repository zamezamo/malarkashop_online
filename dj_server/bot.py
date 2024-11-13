import asyncio
import logging
from dataclasses import dataclass

import uvicorn
from dj_server.asgi import application

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.db.models import Q

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
    #TODO admin panel conversation states
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display start message"""

    query = update.callback_query

    user_id = update.effective_chat.id
    
    if await (models.Admin.objects.filter(admin_id=user_id)).aexists():
        return top_states["ADMIN_PANEL"]

    user, _ = await models.User.objects.aget_or_create(user_id=user_id)
    order, _ = await models.Order.objects.aget_or_create(user_id=user)

    context.user_data["user_id"] = user.user_id
    context.user_data["order_id"] = order.order_id

    keyboard = [
        [
            InlineKeyboardButton("🛍 перейти в каталог", callback_data=top_states["CHOOSE_CATEGORY"])
        ],
        [
            InlineKeyboardButton("🛒 корзина", callback_data=top_states["INTO_CART"])
        ],
        [
            InlineKeyboardButton("🕓 выполняемые заказы", callback_data=top_states["CONFIRMED_ORDER_LIST"])
        ],
        [
            InlineKeyboardButton("✅ завершенные заказы", callback_data=top_states["COMPLETED_ORDER_LIST"])
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if bool(query):

        text = CONFIG.START_TEXT_OVER

        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{CONFIG.URL}/static/img/bot/logo.jpg",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )

    else:

        text = CONFIG.START_TEXT

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
    await query.answer()

    text = CONFIG.CHOOSE_CATEGORY_TEXT

    keyboard = [
        [InlineKeyboardButton(button_name, callback_data=str(top_states["CATEGORY_CARDS"]) + SPLIT + category)] 
            for category, button_name in CONFIG.CATEGORY_CHOICES.items()
    ]
    keyboard += [
        [InlineKeyboardButton("↩️ назад", callback_data=str(top_states["START"]))]
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

    return top_states["CHOOSE_CATEGORY"]


async def category_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all products in this category"""
    
    query = update.callback_query
    await query.answer()

    category = query.data.split(SPLIT)[1]

    parts = models.Part.objects.filter(category=category)

    text = (
        f"*[{CONFIG.CATEGORY_CHOICES[category]}]*\n"
        f"\n\n"
    )

    keyboard = [
        [InlineKeyboardButton("↩️ назад", callback_data=str(top_states["CHOOSE_CATEGORY"]))]
    ]

    if await parts.aexists():
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
    await query.answer()

    callback, category = query.data.split(SPLIT)

    order_id = context.user_data.get("order_id")

    order = await models.Order.objects.aget(order_id=order_id)
    parts = order.parts

    if callback == str(top_states["PRODUCT_CARDS"]):
        part = await models.Part.objects.filter(category=category).afirst()
        part_id = part.part_id
        context.user_data["part_id"] = part_id
    else:
        part_id = context.user_data.get("part_id")

    if callback == str(product_card_states["PREVIOUS"]):
        part = await models.Part.objects.filter(Q(category=category) & Q(part_id__lt=part_id)).alast()
        if part:
            context.user_data["part_id"] = part.part_id

    if callback == str(product_card_states["NEXT"]):
        part = await models.Part.objects.filter(Q(category=category) & Q(part_id__gt=part_id)).afirst()
        if part:
            context.user_data["part_id"] = part.part_id

    if callback == str(product_card_states["REMOVE"]):
        part = await models.Part.objects.aget(part_id=part_id)
        if str(part_id) in parts:
            if parts[str(part_id)] == 1:
                parts.pop(str(part_id))
            else:
                parts[str(part_id)] -= 1
        else:
            #TODO check what is going here in tg chat
            pass
            
    if callback == str(product_card_states["ADD"]):
        part = await models.Part.objects.aget(part_id=part_id)
        if str(part_id) in parts:
            parts[str(part_id)] += 1
        else:
            parts[str(part_id)] = 1

    if callback == str(product_card_states["ENTER_COUNT"]):
        pass

    if callback == str(top_states["INTO_CART"]):
        pass

    if part:
        text = (
            f"*[{CONFIG.CATEGORY_CHOICES[part.category]}]*\n"
            f"\n"
            f"*{part.name}*\n"
            f"_{part.description}_\n\n"
            f"в наличии: *{part.available_count} шт.*"
        )

        img = part.image

        keyboard = [
            [
                InlineKeyboardButton("⬅️", callback_data=str(product_card_states["PREVIOUS"]) + SPLIT + category),
                InlineKeyboardButton("➡️", callback_data=str(product_card_states["NEXT"]) + SPLIT + category),
            ],
            [
                InlineKeyboardButton("➕", callback_data=str(product_card_states["ADD"])),
                InlineKeyboardButton("ввести кол-во", callback_data=str(product_card_states["ENTER_COUNT"])),
                InlineKeyboardButton("➖", callback_data=str(product_card_states["REMOVE"])),
            ],
            [
                InlineKeyboardButton("🛒 в корзину", callback_data=str(top_states["INTO_CART"]))
            ],
            [
                InlineKeyboardButton("↩️ категории", callback_data=str(top_states["CHOOSE_CATEGORY"]))
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_media(
            media=InputMediaPhoto(
                media=img,
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )

    return top_states["PRODUCT_CARDS"]


async def into_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #TODO realize
    pass


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
                    pattern="^" + str(top_states["CHOOSE_CATEGORY"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(top_states["PRODUCT_CARDS"]) + "_[A-Z]{1,8}$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(product_card_states["NEXT"]) + "_[A-Z]{1,8}$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(product_card_states["PREVIOUS"]) + "_[A-Z]{1,8}$"
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
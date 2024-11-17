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
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    ExtBot,
    filters
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
    "REMOVE": 1_3,
    "ENTER_COUNT": 1_4,
    "GET_COUNT": 1_5,
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
    context.user_data["category_part"] = category

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

        keyboard.insert(0, [InlineKeyboardButton("➡️", callback_data=str(top_states["PRODUCT_CARDS"]))])

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

    if update.callback_query is not None:
        query = update.callback_query
        await query.answer()

        callback = query.data
        entered_part_count = None
    else:
        entered_part_count = int(update.message.text)

        callback = None

    category = context.user_data.get("category_part")

    order_id = context.user_data.get("order_id")
    order = await models.Order.objects.aget(order_id=order_id)
    parts = order.parts

    part_id = context.user_data.get("part_id")

    if callback == str(top_states["PRODUCT_CARDS"]):
        part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category)).afirst()
        part_id = part.part_id
        context.user_data["part_id"] = part_id

    if callback == str(product_card_states["PREVIOUS"]):
        part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category) & Q(part_id__lt=part_id)).alast()
        if not part:
            part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category)).alast()
        context.user_data["part_id"] = part.part_id
        
    if callback == str(product_card_states["NEXT"]):
        part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category) & Q(part_id__gt=part_id)).afirst()
        if not part:
            part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category)).afirst()
        context.user_data["part_id"] = part.part_id

    part_deleted_from_catalog = False
    part_not_enough_available_count = False

    if callback == str(product_card_states["REMOVE"]):
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False:
            part_deleted_from_catalog = True
        elif str(part_id) in parts:
            if parts[str(part_id)] - 1 > part.available_count:
                parts[str(part_id)] = part.available_count
                part_not_enough_available_count = True
            if parts[str(part_id)] == 1 or parts[str(part_id)] == 0:
                parts.pop(str(part_id))
            else:
                parts[str(part_id)] -= 1
            await models.Order.objects.filter(order_id=order_id).aupdate(parts=parts)

    if callback == str(product_card_states["ADD"]):
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False:
            part_deleted_from_catalog = True
        else:
            if str(part_id) in parts:
                if parts[str(part_id)] + 1 <= part.available_count:
                    parts[str(part_id)] += 1
                else:
                    parts[str(part_id)] = part.available_count
                    part_not_enough_available_count = True
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=parts)
            elif part.available_count > 0:
                parts[str(part_id)] = 1
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=parts)
            else:
                part_not_enough_available_count = True 

    if entered_part_count is not None:
        await delete_last_msg_from_user(update, context)
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False:
            part_deleted_from_catalog = True
        elif entered_part_count > 0:
            if entered_part_count <= part.available_count:
                parts[str(part_id)] = entered_part_count
            else:
                parts[str(part_id)] = part.available_count
                part_not_enough_available_count = True
            await models.Order.objects.filter(order_id=order_id).aupdate(parts=parts)
        elif parts.get(str(part_id)) is not None:
            parts.pop(str(part_id))
            await models.Order.objects.filter(order_id=order_id).aupdate(parts=parts)

    text = (
        f"*[{CONFIG.CATEGORY_CHOICES[part.category]}]*\n"
        f"\n"
        f"*{part.name}*\n"
        f"_{part.description}_\n\n"
        f"в наличии: *{part.available_count} шт.*\n"
    )

    if str(context.user_data.get("part_id")) in parts:
        text += (
            f"\nв корзине: *{parts[str(context.user_data.get("part_id"))]} шт.*\n"
        )

    if part_deleted_from_catalog:
        text += (
            f"\n_произошла ошибка_\n"
            f"вот так совпадение, товар только что был убран из каталога\n"
            f"чтобы продолжить, выберите другой товар\n"
        )

    if part_not_enough_available_count:
        text += (
            f"\n_произошла ошибка_\n"
            f"выставлено максимально доступное количество товара, либо товар убран из корзины\n"
        )

    img = part.image

    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=str(product_card_states["PREVIOUS"])),
            InlineKeyboardButton("➡️", callback_data=str(product_card_states["NEXT"])),
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

    if callback == str(product_card_states["ADD"]) or callback == str(product_card_states["REMOVE"]):
        try:
            await query.edit_message_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN,
            )
        except:
            pass
    elif callback:
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=img,
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )
    else:
        await ptb_application.bot.edit_message_media(
            chat_id=update.effective_chat.id,
            message_id=context.user_data.get("msg_id"),
            media=InputMediaPhoto(
                media=img,
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )

    return top_states["PRODUCT_CARDS"]


async def ask_for_enter_part_count_in_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user for enter part count in cart"""

    query = update.callback_query
    await query.answer()

    text = CONFIG.ENTER_PARTS_COUNT
    
    await query.edit_message_caption(
        caption=text
    )

    context.user_data["msg_id"] = query.message.message_id

    return product_card_states["ENTER_COUNT"]


async def delete_last_msg_from_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete last message from user"""

    await update.message.delete()


async def into_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cart"""

    #TODO realize
    
    order_id = context.user_data.get("order_id")
    order = await models.Order.objects.aget(order_id=order_id)

    text = (
        f"[ 🛒 корзина ]"
    )

    
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
                CallbackQueryHandler(
                    into_cart,
                    pattern="^" + str(top_states["INTO_CART"]) + "$"
                )
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
                    pattern="^" + str(top_states["PRODUCT_CARDS"]) + "$"
                ),
            ],
            top_states["PRODUCT_CARDS"]: [
                CallbackQueryHandler(
                    choose_category, 
                    pattern="^" + str(top_states["CHOOSE_CATEGORY"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(top_states["PRODUCT_CARDS"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(product_card_states["NEXT"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(product_card_states["PREVIOUS"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(product_card_states["ADD"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(product_card_states["REMOVE"]) + "$"
                ),
                CallbackQueryHandler(
                    ask_for_enter_part_count_in_cart,
                    pattern="^" + str(product_card_states["ENTER_COUNT"]) + "$"
                ),
                CallbackQueryHandler(
                    into_cart,
                    pattern="^" + str(top_states["INTO_CART"]) + "$"
                )
            ],
            # top_states["INTO_CART"]: [
            # ]
            product_card_states["ENTER_COUNT"]: [
                MessageHandler(filters.Regex("^[0-9]{1,}$"), product_cards),
                MessageHandler(~filters.Regex("^[0-9]{1,}$"), delete_last_msg_from_user)
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
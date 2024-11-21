import asyncio
import logging
from datetime import datetime
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
    "COMPLETED_ORDER_LIST": 7,
    "END": 8
}

admin_panel_states = {
    #TODO admin panel conversation states
}

confirmed_order_states = {
    "PREVIOUS": 3_0,
    "NEXT": 3_1,
}

completed_order_states = {
    "PREVIOUS": 4_0,
    "NEXT": 4_1,
}

product_card_states = {
    "PREVIOUS": 5_0,
    "NEXT": 5_1,
    "ADD": 5_2,
    "REMOVE": 5_3,
    "ENTER_COUNT": 5_4,
    "GET_PART_BY_ID": 5_5
}

into_cart_states = {
    "MAKE_ORDER": 6_0,
    "CONFIRM_ORDER": 6_1
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


async def delete_last_msg(update: Update, context=None):
    """Delete last message from user"""

    await update.effective_message.delete()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display start message"""

    query = update.callback_query

    user_id = update.effective_chat.id

    context.user_data.clear()
    
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
        text = CONFIG.START_OVER_TEXT

        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{CONFIG.URL}/static/img/bot/logo.jpg",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )

    else:
        await delete_last_msg(update)

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
    """List of user's confirmed orders"""

    query = update.callback_query
    callback = query.data
    await query.answer()

    order = None
    order_id = context.user_data.get("confirmed_order_id")
    
    user_id = context.user_data.get("user_id")
    user = await models.User.objects.aget(user_id=user_id)

    text = CONFIG.CONFIRMED_ORDERS_TEXT

    if callback == str(top_states["CONFIRMED_ORDER_LIST"]):
        order = await models.ConfirmedOrder.objects.filter(user_id=user).afirst()
        order_id = order.order_id

        context.user_data["confirmed_order_id"] = order_id

    if callback == str(confirmed_order_states["PREVIOUS"]):
        order = await models.ConfirmedOrder.objects.filter(Q(user_id=user) & Q(order_id__lt=order_id)).alast()
        if not order:
            order = await models.ConfirmedOrder.objects.filter(user_id=user).alast()
        if order:
            context.user_data["confirmed_order_id"] = order.order_id

    if callback == str(confirmed_order_states["NEXT"]):
        order = await models.ConfirmedOrder.objects.filter(Q(user_id=user) & Q(order_id__gt=order_id)).afirst()
        if not order:
            order = await models.ConfirmedOrder.objects.filter(user_id=user).afirst()
        if order:
            context.user_data["confirmed_order_id"] = order.order_id

    if order:
        parts = models.Part.objects.filter(part_id__in=list(map(int, order.parts.keys())))

        text += (
            f"- заказ *№{order.order_id}* -\n\n"
            f"оформлен: _{order.ordered_time.strftime("%d.%m.%Y %H:%M")}_\n"
        )

        if order.is_accepted:
            text += f"принят: ✅ _{order.accepted_time.strftime("%d.%m.%Y %d.%m.%Y")}_\n\n"
        else:
            text += f"принят: 🕓 _в обработке_\n\n"

        async for part in parts:
            count = order.parts[str(part.part_id)]
            price = part.price
            cost = count * price

            text += (
                f"●  *{part.name}*\n"
                f"{count}шт. x {price}р. = _{cost}р._\n"
            )

        text += f"\nстоимость: _{order.cost}р._"

        keyboard = [
            [
                InlineKeyboardButton("⬅️", callback_data=str(confirmed_order_states["PREVIOUS"])),
                InlineKeyboardButton("➡️", callback_data=str(confirmed_order_states["NEXT"])),
            ],
            [
                InlineKeyboardButton("↩️ назад", callback_data=str(top_states["START"]))
            ]
        ]
    else:
        text += CONFIG.CONFIRMED_ORDERS_EMPTY_TEXT

        keyboard = [
            [InlineKeyboardButton("↩️ назад", callback_data=str(top_states["START"]))]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if callback == str(top_states["CONFIRMED_ORDER_LIST"]):
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{CONFIG.URL}/static/img/bot/confirmed_orders.jpg",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )
    else:
        try: # ingnore telegram.error.BadRequest: Message on the same message
            await query.edit_message_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

    return top_states["CONFIRMED_ORDER_LIST"]


async def completed_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List of user's completed orders"""
    


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

    parts = models.Part.objects.filter(Q(is_available=True) & Q(category=category))

    text = (
        f"*[{CONFIG.CATEGORY_CHOICES[category]}]*\n"
        f"\n\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("↩️ назад", callback_data=str(top_states["CHOOSE_CATEGORY"]))
        ]
    ]

    if await parts.aexists():
        text += (
            f"В наличии:\n\n"
        )

        keyboard.insert(0, [InlineKeyboardButton("➡️", callback_data=str(top_states["PRODUCT_CARDS"]))])

        async for part in parts:
            text += f"●  *{part.name}*, {part.available_count}шт.\n"

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

    part_id = context.user_data.get("part_id")
    part = None

    part_deleted_from_catalog = False
    part_not_enough_available_count = False

    if callback == str(top_states["PRODUCT_CARDS"]):
        part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category)).afirst()
        part_id = part.part_id
        
        context.user_data["part_id"] = part_id

        if str(part_id) in order.parts:
            if order.parts[str(part_id)] > part.available_count:
                order.parts[str(part_id)] = part.available_count
                part_not_enough_available_count = True
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)

    if callback == str(product_card_states["PREVIOUS"]):
        part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category) & Q(part_id__lt=part_id)).alast()

        if not part:
            part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category)).alast()

        if part:
            context.user_data["part_id"] = part.part_id

            if str(part.part_id) in order.parts:
                if order.parts[str(part.part_id)] > part.available_count:
                    order.parts[str(part.part_id)] = part.available_count
                    part_not_enough_available_count = True
                    await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
        else:
            await start(update, context)
            return top_states["START"]
  
    if callback == str(product_card_states["NEXT"]):
        part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category) & Q(part_id__gt=part_id)).afirst()

        if not part:
            part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category)).afirst()

        if part:
            context.user_data["part_id"] = part.part_id

            if str(part.part_id) in order.parts:
                if order.parts[str(part.part_id)] > part.available_count:
                    order.parts[str(part.part_id)] = part.available_count
                    part_not_enough_available_count = True
                    await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
        else:
            await start(update, context)

    if callback == str(product_card_states["REMOVE"]):
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False:
            part_deleted_from_catalog = True
        elif str(part_id) in order.parts:
            if order.parts[str(part_id)] - 1 > part.available_count:
                order.parts[str(part_id)] = part.available_count
                part_not_enough_available_count = True
            elif order.parts[str(part_id)] > 1:
                order.parts[str(part_id)] -= 1
            else:
                order.parts.pop(str(part_id))
            await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)

    if callback == str(product_card_states["ADD"]):
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False:
            part_deleted_from_catalog = True
        else:
            if str(part_id) in order.parts:
                if order.parts[str(part_id)] + 1 <= part.available_count:
                    order.parts[str(part_id)] += 1
                else:
                    order.parts[str(part_id)] = part.available_count
                    part_not_enough_available_count = True
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
            elif part.available_count > 0:
                order.parts[str(part_id)] = 1
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
            else:
                part_not_enough_available_count = True 

    if entered_part_count is not None:
        await delete_last_msg(update)
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False:
            part_deleted_from_catalog = True
        elif entered_part_count > 0:
            if entered_part_count <= part.available_count:
                order.parts[str(part_id)] = entered_part_count
            else:
                order.parts[str(part_id)] = part.available_count
                part_not_enough_available_count = True
            await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
        elif order.parts.get(str(part_id)) is not None:
            order.parts.pop(str(part_id))
            await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)

    text = (
        f"*[{CONFIG.CATEGORY_CHOICES[part.category]}]*\n"
        f"\n"
        f"*{part.name}*\n"
        f"_{part.description}_\n\n"
        f"цена за 1шт.: *{part.price}р.*\n"
        f"в наличии: *{part.available_count} шт.*\n"
    )

    if str(part.part_id) in order.parts:
        count = order.parts[str(part.part_id)]
        text += (
            f"\nв корзине: *{count}шт.*\n"
            f"на *{count * part.price}р.*\n"
        )

    if part_deleted_from_catalog:
        text += CONFIG.PART_DELETED_FROM_CATALOG_ERROR_TEXT

    if part_not_enough_available_count:
        text += CONFIG.PART_NOT_ENOUGH_AVAILABLE_COUNT_ERROR_TEXT

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
        try: # ingnore telegram.error.BadRequest: Message on the same message
            await query.edit_message_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN,
            )
        except:
            pass
    elif callback:
        try: # ingnore telegram.error.BadRequest: Message on the same message
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=img,
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN,
                ),
                reply_markup=reply_markup
            )
        except:
            pass
    else:
        await context.bot.edit_message_media(
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

    text = CONFIG.ENTER_PARTS_COUNT_TEXT
    
    await query.edit_message_caption(
        caption=text,
        parse_mode=ParseMode.MARKDOWN
    )

    context.user_data["msg_id"] = query.message.message_id

    return product_card_states["GET_PART_BY_ID"]


async def confirm_order_to_db(update: Update, context: ContextTypes.DEFAULT_TYPE, order: models.Order):
    """Add order to confirmed orders in db and change the quantity of ordered parts in catalog"""

    user_id = context.user_data.get("user_id")
    context.user_data.clear()
    user = await models.User.objects.aget(user_id=user_id)

    await models.ConfirmedOrder.objects.acreate(
        order_id = order.order_id,
        user_id = user,
        parts = order.parts,
        cost = order.cost,
        ordered_time = datetime.now()
    )

    parts = models.Part.objects.filter(part_id__in=list(map(int, order.parts.keys())))

    async for part in parts:
        count = part.available_count - order.parts[str(part.part_id)]
        await models.Part.objects.filter(part_id=part.part_id).aupdate(available_count=count)

    await models.Order.objects.filter(order_id=order.order_id).adelete()

    text = (
        f"заказ *№{order.order_id}* оформлен\n"
        f"ожидайте уведомления об его подтверждении\n\n"
        f"также статус заказа можно посмотреть в\n"
        f"*[🕓 выполняемые заказы]*\n\n"
        f"/start - перейти в профиль"
    )

    await delete_last_msg(update)

    await context.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
    
    logger.info(f"[PTB] Order #{order.order_id} from user {user_id} confirmed")


async def into_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cart"""

    query = update.callback_query
    callback = query.data
    await query.answer()
    
    order_id = context.user_data.get("order_id")
    order = await models.Order.objects.aget(order_id=order_id)
    order.cost = 0

    text = CONFIG.INTO_CART_TEXT
    reply_markup = None

    if bool(order.parts):
        text += CONFIG.PARTS_PRESENTED_IN_CART_TEXT

        parts = models.Part.objects.filter(part_id__in=list(map(int, order.parts.keys())))

        if callback == str(top_states["INTO_CART"]):
            async for part in parts:
                count = order.parts[str(part.part_id)]
                price = part.price
                cost = count * price
                text += (
                    f"●  *{part.name}*\n"
                    f"{count}шт. x {price}р. = _{cost}р._\n"
                )
                order.cost += cost

            text += (
                f"\n*итого:* _{order.cost}р._\n"
            )

            keyboard = [
                [
                    InlineKeyboardButton("📦 оформить заказ", callback_data=str(into_cart_states["MAKE_ORDER"]))
                ],
                [
                    InlineKeyboardButton("↩️ в начало", callback_data=str(top_states["START"]))
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

        if callback == str(into_cart_states["MAKE_ORDER"]):
            async for part in parts:
                count = order.parts[str(part.part_id)]
                price = part.price
                cost = count * price
                text += (
                    f"●  *{part.name}*\n"
                    f"{count}шт. x {price}р. = _{cost}р._\n"
                )

                order.cost += cost

            text += (
                f"\n*итого:* _{order.cost}р._\n"
            )

            text += CONFIG.ORDER_CONFIRMATION_TEXT

            keyboard = [
                [
                    InlineKeyboardButton("✅ да", callback_data=str(into_cart_states["CONFIRM_ORDER"]))
                ],
                [
                    InlineKeyboardButton("↩️ в начало", callback_data=str(top_states["START"]))
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

        if callback == str(into_cart_states["CONFIRM_ORDER"]):

            parts_id_deleted_from_catalog = list()
            parts_id_not_enough_available_count = list()

            async for part in parts:
                part_id = part.part_id

                if part.is_available == False:
                    text += (
                        f"●  *{part.name}*\n"
                        f"{order.parts[str(part_id)]}шт.\n"
                        f"_[удалено из каталога]_,\n"
                    )

                    parts_id_deleted_from_catalog.append(part_id)
                    order.parts.pop(str(part_id))
                else:
                    count = order.parts[str(part_id)]
                    price = part.price
                    cost = count * price

                    if order.parts[str(part_id)] > part.available_count:
                        text += (
                            f"●  *{part.name}*\n"
                            f"{count}шт. x {price}р. = _{cost}р._\n"
                            f"_[выст. макс. дост. кол-во]_,\n"
                        )

                        order.parts[str(part_id)] = part.available_count
                        parts_id_not_enough_available_count.append(part_id)
                    else:
                        text += (
                            f"●  *{part.name}*\n"
                            f"{count}шт. x {price}р. = _{cost}р._\n"
                        )
                        order.cost += cost

            text += (
                f"\n*итого:* _{order.cost}р._\n"
            )

            if len(parts_id_deleted_from_catalog) or len(parts_id_not_enough_available_count):   
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)

                keyboard = [
                    [
                        InlineKeyboardButton("✅ ок", callback_data=str(into_cart_states["MAKE_ORDER"]))
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                text += CONFIG.ORDER_CONFIRMATION_ERROR_TEXT
            else:
                await confirm_order_to_db(update, context, order)
                return top_states["END"]

    else:
        text += CONFIG.EMPTY_CART_TEXT
        keyboard = [   
            [
                InlineKeyboardButton("↩️ в начало", callback_data=str(top_states["START"]))
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_caption(
            caption=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    if callback == str(top_states["INTO_CART"]):
        try: # ingnore telegram.error.BadRequest: Message on the same message
            await query.edit_message_media(
                    media=InputMediaPhoto(
                        media=f"{CONFIG.URL}/static/img/bot/cart.jpg",
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN,
                    ),
                    reply_markup=reply_markup
                )
        except:
            pass
        
    return top_states["INTO_CART"]

    
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
                ),
                CallbackQueryHandler(
                    confirmed_order_list, 
                    pattern="^" + str(top_states["CONFIRMED_ORDER_LIST"]) + "$"
                )
            ],
            top_states["CONFIRMED_ORDER_LIST"]: [
                CallbackQueryHandler(
                    start, 
                    pattern="^" + str(top_states["START"]) + "$"
                ),
                CallbackQueryHandler(
                    confirmed_order_list, 
                    pattern="^" + str(confirmed_order_states["PREVIOUS"]) + "$"
                ),
                CallbackQueryHandler(
                    confirmed_order_list, 
                    pattern="^" + str(confirmed_order_states["NEXT"]) + "$"
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
            top_states["INTO_CART"]: [
                CallbackQueryHandler(
                    start,
                    pattern="^" + str(top_states["START"]) + "$"
                ),
                CallbackQueryHandler(
                    into_cart,
                    pattern="^" + str(into_cart_states["MAKE_ORDER"]) + "$"
                ),
                CallbackQueryHandler(
                    into_cart,
                    pattern="^" + str(into_cart_states["CONFIRM_ORDER"]) + "$"
                )
            ],
            top_states["END"]: [],
            product_card_states["GET_PART_BY_ID"]: [
                MessageHandler(filters.Regex("^[0-9]{1,}$"), product_cards),
                MessageHandler(~filters.Regex("^[0-9]{1,}$"), delete_last_msg),
            ],
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
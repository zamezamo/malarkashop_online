import asyncio
import logging
from datetime import datetime, timezone
from dataclasses import dataclass

import uvicorn
from dj_server.asgi import application

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
    "EMPTY_CATEGORY": 3,
    "PRODUCT_CARDS": 4,
    "INTO_CART": 5,
    "CONFIRMED_ORDER_LIST": 6,
    "COMPLETED_ORDER_LIST": 7,
    "END": 8
}

admin_panel_states = {
    "NOTIFICATIONS_ON_OFF": 2_0,
    "ALL_CONFIRMED_ORDER_LIST": 2_1,
    "ALL_COMPLETED_ORDER_LIST": 2_2
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


async def delete_last_msg(update: Update, context=None):
    """Delete last message from user"""

    await update.effective_message.delete()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display start message"""

    query = update.callback_query

    user_id = update.effective_chat.id
    username = update.effective_chat.username
    if not username:
        username = str(user_id)

    context.user_data.clear()
    
    if await (models.Admin.objects.filter(admin_id=user_id)).aexists():
        await admin_panel(update, context)
        return top_states["ADMIN_PANEL"]

    user, _ = await models.User.objects.aupdate_or_create(user_id=user_id, username=username)
    order, _ = await models.Order.objects.aget_or_create(user_id=user)

    if user.username != username:
        await models.User.objects.filter(user_id=user_id).aupdate(username=username)

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
    "Admin panel"

    callback = None

    if update.callback_query is not None:
        query = update.callback_query
        await query.answer()

        callback = query.data
    else:
        await delete_last_msg(update)

    text = CONFIG.ADMIN_PANEL_TEXT

    admin = await models.Admin.objects.aget(admin_id=update.effective_chat.id)

    if callback == str(admin_panel_states["NOTIFICATIONS_ON_OFF"]):
        admin.is_notification_enabled = not admin.is_notification_enabled
        await models.Admin.objects.filter(admin_id=admin.admin_id).aupdate(is_notification_enabled=admin.is_notification_enabled)

    text += f"*[статистика на сегодня]*\n\n"

    confirmed_orders_count = await models.ConfirmedOrder.objects.filter(is_accepted=False).acount()
    accepted_orders_count = await models.ConfirmedOrder.objects.filter(is_accepted=True).acount()
    completed_orders_count = await models.CompletedOrder.objects.all().acount()
    available_parts_count = await models.Part.objects.filter(is_available=True).acount()
        
    text += (
        f"🕓 *{confirmed_orders_count} заказов* ожидают подтверждения\n\n"
        f"📦 *{accepted_orders_count} заказов* доставляются\n\n"
        f"✅ *{completed_orders_count} заказов* доставлено\n\n"
        f"🛠 *{available_parts_count} товаров* доступно в каталоге\n\n"
    )

    text += f"\n*[уведомления о заказах]*\n"

    if admin.is_notification_enabled:
        text += f"🔔 включены"
    else:
        text += f"🔕 выключены"


    keyboard = [
        [
            InlineKeyboardButton("🔄 обновить информацию", callback_data=str(top_states["ADMIN_PANEL"]))
        ],
        [
            InlineKeyboardButton("🔔 вкл/выкл уведомления о заказах", callback_data=str(admin_panel_states["NOTIFICATIONS_ON_OFF"]))
        ],
        [
            InlineKeyboardButton("🕓 выполняемые заказы", callback_data=str(admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]))
        ],
        [
            InlineKeyboardButton("✅ завершенные заказы", callback_data=str(admin_panel_states["ALL_COMPLETED_ORDER_LIST"]))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if callback is None:
        await update.message.reply_photo(
                photo=f"{CONFIG.URL}/static/img/bot/admin_panel.jpg",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
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

    return top_states["ADMIN_PANEL"]


async def all_confirmed_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    "List of all confirmed orders from all users"

    #TODO realize

    text = CONFIG.CONFIRMED_ORDERS_TEXT

    keyboard = [
        [
            InlineKeyboardButton("🔍 просмотреть заказ по №", callback_data=str(top_states["ADMIN_PANEL"]))
        ],
        [
            InlineKeyboardButton("↩️ назад", callback_data=str(top_states["ADMIN_PANEL"]))
        ]
    ]

    confirmed_orders = models.ConfirmedOrder.objects.order_by()
    
    return admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]


async def all_completed_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    "List of all completed orders from all users"

    #TODO realize

    text = CONFIG.CONFIRMED_ORDERS_TEXT

    keyboard = [
        [
            InlineKeyboardButton("🔍 просмотреть заказ по №", callback_data=str(top_states["ADMIN_PANEL"]))
        ],
        [
            InlineKeyboardButton("↩️ назад", callback_data=str(top_states["ADMIN_PANEL"]))
        ]
    ]

    completed_orders = None

    return admin_panel_states["ALL_COMPLETED_ORDER_LIST"]


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
        if order:
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

        ordered_time = order.ordered_time + CONFIG.TZ_OFFSET

        text += (
            f"- заказ *№{order.order_id}* -\n\n"
            f"оформлен: _{ordered_time.strftime("%d.%m.%Y %H:%M")}_\n"
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
        text += CONFIG.EMPTY_TEXT

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

    query = update.callback_query
    callback = query.data
    await query.answer()

    order = None
    order_id = context.user_data.get("completed_order_id")
    
    user_id = context.user_data.get("user_id")
    user = await models.User.objects.aget(user_id=user_id)

    text = CONFIG.COMPLETED_ORDERS_TEXT

    if callback == str(top_states["COMPLETED_ORDER_LIST"]):
        order = await models.CompletedOrder.objects.filter(user_id=user).afirst()
        if order:
            order_id = order.order_id

        context.user_data["completed_order_id"] = order_id

    if callback == str(completed_order_states["PREVIOUS"]):
        order = await models.CompletedOrder.objects.filter(Q(user_id=user) & Q(order_id__lt=order_id)).alast()
        if not order:
            order = await models.CompletedOrder.objects.filter(user_id=user).alast()
        if order:
            context.user_data["completed_order_id"] = order.order_id

    if callback == str(completed_order_states["NEXT"]):
        order = await models.CompletedOrder.objects.filter(Q(user_id=user) & Q(order_id__gt=order_id)).afirst()
        if not order:
            order = await models.CompletedOrder.objects.filter(user_id=user).afirst()
        if order:
            context.user_data["completed_order_id"] = order.order_id

    if order:
        parts = models.Part.objects.filter(part_id__in=list(map(int, order.parts.keys())))

        ordered_time = order.ordered_time + CONFIG.TZ_OFFSET
        accepted_time = order.accepted_time + CONFIG.TZ_OFFSET
        completed_time = order.completed_time + CONFIG.TZ_OFFSET

        text += (
            f"- заказ *№{order.order_id}* -\n\n"
            f"оформлен: _{ordered_time.strftime("%d.%m.%Y %H:%M")}_\n"
            f"принят: _{accepted_time.strftime("%d.%m.%Y %H:%M")}_\n"
            f"завершён: _{completed_time.strftime("%d.%m.%Y %H:%M")}_\n\n"
        )

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
                InlineKeyboardButton("⬅️", callback_data=str(completed_order_states["PREVIOUS"])),
                InlineKeyboardButton("➡️", callback_data=str(completed_order_states["NEXT"])),
            ],
            [
                InlineKeyboardButton("↩️ назад", callback_data=str(top_states["START"]))
            ]
        ]
    else:
        text += CONFIG.EMPTY_TEXT

        keyboard = [
            [InlineKeyboardButton("↩️ назад", callback_data=str(top_states["START"]))]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if callback == str(top_states["COMPLETED_ORDER_LIST"]):
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{CONFIG.URL}/static/img/bot/completed_orders.jpg",
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

    return top_states["COMPLETED_ORDER_LIST"]


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display a message to the user to select a product category"""

    query = update.callback_query
    await query.answer()

    text = CONFIG.CHOOSE_CATEGORY_TEXT

    keyboard = [
        [InlineKeyboardButton(button_name, callback_data=str(top_states["PRODUCT_CARDS"]) + SPLIT + category)] 
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


async def empty_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display message that this category doesn't have parts"""

    category = context.user_data.get("category_part")

    text = f"*[{CONFIG.CATEGORY_CHOICES[category]}]*\n\n\n"
    text += CONFIG.EMPTY_TEXT

    keyboard = [
        [InlineKeyboardButton("↩️ назад", callback_data=str(top_states["CHOOSE_CATEGORY"]))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_media(
        media=InputMediaPhoto(
            media=f"{CONFIG.URL}/static/img/bot/cart.jpg",
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
        ),
        reply_markup=reply_markup
    )

    return top_states["EMPTY_CATEGORY"]


async def product_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all info about chosen product in this category"""

    category = context.user_data.get("category_part")
    first_call = False

    if update.callback_query is not None:
        query = update.callback_query
        
        await query.answer()

        callback = query.data

        if len(callback) > 2:
            category = callback.split(SPLIT)[1]
            context.user_data["category_part"] = category
            first_call = True

        entered_part_count = None
    else:
        entered_part_count = int(update.message.text)

        callback = None

    order_id = context.user_data.get("order_id")
    order = await models.Order.objects.aget(order_id=order_id)

    part_id = context.user_data.get("part_id")
    part = None

    part_deleted_from_catalog = False
    part_not_enough_available_count = False

    if callback == str(top_states["PRODUCT_CARDS"]) or first_call:
        part = await models.Part.objects.filter(Q(is_available=True) & Q(category=category)).afirst()

        if not part:
            await empty_category(update, context)
            return top_states["EMPTY_CATEGORY"]

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
            await empty_category(update, context)
            return top_states["EMPTY_CATEGORY"]
  
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
            await empty_category(update, context)
            return top_states["EMPTY_CATEGORY"]

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
        ordered_time = datetime.now(timezone.utc)
    )

    parts = models.Part.objects.filter(part_id__in=list(map(int, order.parts.keys())))

    async for part in parts:
        count = part.available_count - order.parts[str(part.part_id)]
        await models.Part.objects.filter(part_id=part.part_id).aupdate(available_count=count)
        if count == 0:
            await models.Part.objects.filter(part_id=part.part_id).aupdate(is_available=False)

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
    
    text_to_admin = f"поступил заказ *№{order.order_id}* от @{user.username}"
    
    admins_with_notifacations_enabled = models.Admin.objects.filter(is_notification_enabled=True)

    async for admin in admins_with_notifacations_enabled:
        await context.bot.send_message(
            chat_id=admin.admin_id,
            text=text_to_admin,
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
        text += CONFIG.EMPTY_TEXT
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


# Set up PTB application and a web application for handling the incoming requests.
context_types = ContextTypes(context=CallbackContext)
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
                ),
                CallbackQueryHandler(
                    completed_order_list, 
                    pattern="^" + str(top_states["COMPLETED_ORDER_LIST"]) + "$"
                )   
            ],
            top_states["ADMIN_PANEL"]: [
                CallbackQueryHandler(
                    admin_panel, 
                    pattern="^" + str(top_states["ADMIN_PANEL"]) + "$"
                ),
                CallbackQueryHandler(
                    admin_panel, 
                    pattern="^" + str(admin_panel_states["NOTIFICATIONS_ON_OFF"]) + "$"
                ),
                CallbackQueryHandler(
                    all_confirmed_order_list, 
                    pattern="^" + str(admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]) + "$"
                ),
                CallbackQueryHandler(
                    all_completed_order_list, 
                    pattern="^" + str(admin_panel_states["ALL_COMPLETED_ORDER_LIST"]) + "$"
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
                )
            ],
            top_states["COMPLETED_ORDER_LIST"]: [
                CallbackQueryHandler(
                    start, 
                    pattern="^" + str(top_states["START"]) + "$"
                ),
                CallbackQueryHandler(
                    completed_order_list, 
                    pattern="^" + str(completed_order_states["PREVIOUS"]) + "$"
                ),
                CallbackQueryHandler(
                    completed_order_list, 
                    pattern="^" + str(completed_order_states["NEXT"]) + "$"
                )
            ],
            top_states["CHOOSE_CATEGORY"]: [
                CallbackQueryHandler(
                    start, 
                    pattern="^" + str(top_states["START"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(top_states["PRODUCT_CARDS"]) + "_[A-Z]{1,8}$"
                )
            ],
            top_states["EMPTY_CATEGORY"]: [
                CallbackQueryHandler(
                    choose_category, 
                    pattern="^" + str(top_states["CHOOSE_CATEGORY"]) + "$"
                )
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
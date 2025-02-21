import asyncio
import logging
from datetime import datetime, timezone

import uvicorn
from dj_server.asgi import application
from asgiref.sync import sync_to_async

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
from dj_server.credentials import TOKEN, URL, PORT

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
    "USER_PROFILE_EDIT": 2,
    "CHOOSE_CATEGORY": 3,
    "EMPTY_CATEGORY": 4,
    "PRODUCT_CARDS": 5,
    "INTO_CART": 6,
    "CONFIRMED_ORDER_LIST": 7,
    "COMPLETED_ORDER_LIST": 8,
    "END": 9
}

user_profile_edit_states = {
    "ENTER_NAME": 2_0,
    "ENTER_PHONE_NUMBER": 2_1,
    "ENTER_DELIVERY_ADDRESS": 2_2,
    "GET_NAME": 2_3,
    "GET_PHONE_NUMBER": 2_4,
    "GET_DELIVERY_ADDRESS": 2_5,
}

admin_panel_states = {
    "NOTIFICATIONS_ON_OFF": 3_0,
    "ALL_CONFIRMED_ORDER_LIST": 3_1
}

all_confirmed_order_states = {
    "PREVIOUS": 4_0,
    "NEXT": 4_1,
    "ACCEPT_ORDER": 4_2,
    "COMPLETE_ORDER": 4_3,
    "CANCEL_ORDER": 4_4
}

confirmed_order_states = {
    "PREVIOUS": 5_0,
    "NEXT": 5_1,
}

completed_order_states = {
    "PREVIOUS": 6_0,
    "NEXT": 6_1,
}

product_card_states = {
    "PREVIOUS": 7_0,
    "NEXT": 7_1,
    "ADD": 7_2,
    "REMOVE": 7_3,
    "ENTER_COUNT": 7_4,
    "GET_PART_BY_ID": 7_5
}

into_cart_states = {
    "MAKE_ORDER": 8_0,
    "CONFIRM_ORDER": 8_1,
    "EMPTY_CART": 8_2
}


async def delete_last_msg(update: Update, context=None):
    """Delete last message from user"""

    await update.effective_message.delete()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display start message"""

    context.user_data.clear()

    query = update.callback_query

    user = None
    user_id = update.effective_chat.id
    tg_username = update.effective_chat.username
    try:
        user = await models.User.objects.aget(user_id=user_id)
    except:
        context.user_data["is_user_registration"] = True

        await user_profile_edit(update, context)
        await delete_last_msg(update)

        return top_states["USER_PROFILE_EDIT"]
    
    if (tg_username is not None) and (('@' + tg_username) != user.username):
        await models.User.objects.filter(user_id=user_id).aupdate(username=tg_username)
    
    order = None
    try:
        order = await models.Order.objects.aget(user=user)
    except:
        order = await models.Order.objects.acreate(user=user)
        logger.info(f"[PTB] Order [id: {order.order_id}] from user [{user}] created")

    text = (
        f"*{CONFIG.TITLE}*\n"
        f"приветствуем, *{await sync_to_async(lambda: user.name)()}*!\n\n"
        f"подписывайтесь на наш [канал]({CONFIG.CHANNEL_LINK})!\n\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("🛍 перейти в каталог", callback_data=str(top_states["CHOOSE_CATEGORY"]))
        ],
        [
            InlineKeyboardButton("🛒 корзина", callback_data=str(top_states["INTO_CART"]))
        ],
        [
            InlineKeyboardButton("🕓 выполняемые заказы", callback_data=str(top_states["CONFIRMED_ORDER_LIST"]))
        ],
        [
            InlineKeyboardButton("✅ завершенные заказы", callback_data=str(top_states["COMPLETED_ORDER_LIST"]))
        ],
        [
            InlineKeyboardButton("📝 редактировать профиль", callback_data=str(top_states["USER_PROFILE_EDIT"]))
        ]
    ]
    
    if await models.Admin.objects.filter(admin_id=user_id).aexists():
        keyboard.insert(
            0,
            [InlineKeyboardButton("[🪪 admin] войти", callback_data=str(top_states["ADMIN_PANEL"]))]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    context.user_data["user_id"] = user.user_id
    context.user_data["order_id"] = order.order_id

    if bool(query):

        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{URL}/static/img/bot/malarka_shop_bot_logo.jpg?a={CONFIG.TIMESTAMP_START}",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )

    else:
        await delete_last_msg(update)

        await update.message.reply_photo(
            photo=f"{URL}/static/img/bot/malarka_shop_bot_logo.jpg?a={CONFIG.TIMESTAMP_START}",
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    return top_states["START"]


async def user_profile_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit user profile settings"""

    callback = None
    if update.callback_query is not None:
        query = update.callback_query
        await query.answer()

        callback = query.data

    user_id = update.effective_chat.id
    tg_username = update.effective_chat.username

    if tg_username is None:
        tg_username = "tg-" + str(user_id)
    else:
        tg_username = "@" + tg_username

    user_name = context.user_data.get("user_name")
    user_phone_number = context.user_data.get("user_phone_number")
    user_delivery_address = context.user_data.get("user_delivery_address")

    keyboard = [
        [
            InlineKeyboardButton("👤 указать имя", callback_data=str(user_profile_edit_states["ENTER_NAME"]))
        ],
        [
            InlineKeyboardButton("📞 указать моб. телефон", callback_data=str(user_profile_edit_states["ENTER_PHONE_NUMBER"]))
        ],
        [
            InlineKeyboardButton("📍 указать адрес доставки", callback_data=str(user_profile_edit_states["ENTER_DELIVERY_ADDRESS"]))
        ]
    ]

    if context.user_data.get("is_user_registration"):
        text = (
            f"добро пожаловать в *{CONFIG.TITLE}*!\n\n"
            f"подписывайтесь на наш [канал]({CONFIG.CHANNEL_LINK})!\n\n"
            f"📝 *регистрация пользователя*\n\n"
        )

        if user_name:
            text += f"👤 *ваше имя*: _{user_name}_\n"
        else:
            text += f"👤 *ваше имя*: _не указано_\n"

        if user_phone_number:
            text += f"📞 *телефон*: _+375{user_phone_number}_\n"
        else:
            text += f"📞 *телефон*: _не указан_\n"

        if user_delivery_address:
            text += f"📍 *адрес доставки*: _{user_delivery_address}_\n"
        else:
            text += f"📍 *адрес доставки*: _не указан_\n"

        if user_name and user_phone_number and user_delivery_address:
            keyboard.append(
                [InlineKeyboardButton("✅ готово", callback_data=str(top_states["START"]))]
            )

            if await models.User.objects.filter(user_id=user_id).aexists():
                await models.User.objects.filter(user_id=user_id).aupdate(
                    username=tg_username,
                    name=user_name,
                    phone_number=user_phone_number,
                    delivery_address=user_delivery_address
                )
                logger.info(f"[PTB] User [id: {user_id}, username: {tg_username}, name: {user_name}] updated")
            else:
                await models.User.objects.acreate(
                    user_id=user_id,
                    username=tg_username,
                    name=user_name,
                    phone_number=user_phone_number,
                    delivery_address=user_delivery_address
                )
                logger.info(f"[PTB] User [id: {user_id}, username: {tg_username}, name: {user_name}] registered")

    else:
        text = (
            f"*{CONFIG.TITLE}*\n\n"
            f"📝 *редактирование профиля*\n\n"
        )

        keyboard.append(
            [InlineKeyboardButton("↩️ назад", callback_data=str(top_states["START"]))]
        )

        user = await models.User.objects.aget(user_id=user_id)

        if user_name:
            user.name = user_name

        if user_phone_number:
            user.phone_number = user_phone_number

        if user_delivery_address:
            user.delivery_address = user_delivery_address

        text += (
            f"👤 *ваше имя*: _{user.name}_\n"
            f"📞 *телефон*: _+375{user.phone_number}_\n"
            f"📍 *адрес доставки*: _{user.delivery_address}_\n"
        )

        await models.User.objects.filter(user_id=user_id).aupdate(
                username=tg_username,
                name=user.name,
                phone_number=user.phone_number,
                delivery_address=user.delivery_address
            )

    reply_markup = InlineKeyboardMarkup(keyboard)

    if context.user_data.get("msg_id") == None and callback == None:
        await update.message.reply_photo(
            photo=f"{URL}/static/img/bot/malarka_shop_bot_user_profile_edit.jpg?a={CONFIG.TIMESTAMP_START}",
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    elif callback == str(top_states["USER_PROFILE_EDIT"]):
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{URL}/static/img/bot/malarka_shop_bot_user_profile_edit.jpg?a={CONFIG.TIMESTAMP_START}",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )
    else:
        await context.bot.edit_message_media(
            chat_id=user_id,
            message_id=context.user_data.get("msg_id"),
            media=InputMediaPhoto(
                media=f"{URL}/static/img/bot/malarka_shop_bot_user_profile_edit.jpg?a={CONFIG.TIMESTAMP_START}",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )

    return top_states["USER_PROFILE_EDIT"]


async def ask_for_enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user for enter his name"""

    query = update.callback_query
    await query.answer()

    text = (
        f"как к вам обращаться? (макс. 64 симв.)"
    )
    
    await query.edit_message_caption(
        caption=text,
        parse_mode=ParseMode.MARKDOWN
    )

    context.user_data["msg_id"] = query.message.message_id

    return user_profile_edit_states["GET_NAME"]


async def ask_for_enter_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user for enter his phone number"""

    query = update.callback_query
    await query.answer()

    text = (
        f"ваш телефон?\n"
        f"в следующем формате: _(25, 29, 33, 44)xxxxxxx_"
        f"(9 цифр после +375)"
    )
    
    await query.edit_message_caption(
        caption=text,
        parse_mode=ParseMode.MARKDOWN
    )

    context.user_data["msg_id"] = query.message.message_id

    return user_profile_edit_states["GET_PHONE_NUMBER"]


async def ask_for_enter_delivery_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user for enter delivery address"""

    query = update.callback_query
    await query.answer()

    text = (
        f"адрес доставки? (макс. 128 симв.)"
    )
    
    await query.edit_message_caption(
        caption=text,
        parse_mode=ParseMode.MARKDOWN
    )

    context.user_data["msg_id"] = query.message.message_id

    return user_profile_edit_states["GET_DELIVERY_ADDRESS"]


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get entered user's name"""

    await delete_last_msg(update)

    context.user_data["user_name"] = update.message.text
    await user_profile_edit(update, context)

    return top_states["USER_PROFILE_EDIT"]


async def get_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get entered user's phone number"""

    await delete_last_msg(update)

    context.user_data["user_phone_number"] = update.message.text
    await user_profile_edit(update, context)

    return top_states["USER_PROFILE_EDIT"]
  

async def get_delivery_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get entered user's delivery address"""

    await delete_last_msg(update)

    context.user_data["user_delivery_address"] = update.message.text
    await user_profile_edit(update, context)

    return top_states["USER_PROFILE_EDIT"]


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    "Admin panel"

    query = update.callback_query
    await query.answer()

    callback = query.data

    text = (
        f"*{CONFIG.TITLE}*\n"
        f"*[admin панель]*\n"
        f"_успешно авторизовано_\n\n\n"
    )

    admin = await models.Admin.objects.aget(admin_id=context.user_data.get("user_id"))

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
            InlineKeyboardButton("[🪪 admin] выйти", callback_data=str(top_states["START"]))
        ],
        [
            InlineKeyboardButton("🔄 обновить информацию", callback_data=str(top_states["ADMIN_PANEL"]))
        ],
        [
            InlineKeyboardButton("🔔 вкл/выкл уведомления о заказах", callback_data=str(admin_panel_states["NOTIFICATIONS_ON_OFF"]))
        ],
        [
            InlineKeyboardButton("🕓 выполняемые заказы", callback_data=str(admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try: # ingnore telegram.error.BadRequest: Message on the same message
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{URL}/static/img/bot/malarka_shop_bot_admin_panel.jpg?a={CONFIG.TIMESTAMP_START}",
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            ),
            reply_markup=reply_markup
        )
    except:
        pass

    return top_states["ADMIN_PANEL"]


async def all_confirmed_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    "List of all confirmed orders from all users"

    query = update.callback_query
    callback = query.data
    await query.answer()

    order = None
    order_id = context.user_data.get("all_confirmed_order_id")

    text = (
        f"*[🕓 выполняемые заказы]*\n\n\n"
    )

    if callback == str(admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]):
        order = await models.ConfirmedOrder.objects.all().afirst()

        if order:
            order_id = order.order_id

        context.user_data["all_confirmed_order_id"] = order_id

    if callback == str(all_confirmed_order_states["PREVIOUS"]):
        order = await models.ConfirmedOrder.objects.filter(order_id__lt=order_id).alast()
        if not order:
            order = await models.ConfirmedOrder.objects.all().alast()
        if order:
            context.user_data["all_confirmed_order_id"] = order.order_id

    if callback == str(all_confirmed_order_states["NEXT"]):
        order = await models.ConfirmedOrder.objects.filter(order_id__gt=order_id).afirst()
        if not order:
            order = await models.ConfirmedOrder.objects.all().afirst()
        if order:
            context.user_data["all_confirmed_order_id"] = order.order_id

    if callback == str(all_confirmed_order_states["CANCEL_ORDER"]):
        try:
            order = await models.ConfirmedOrder.objects.aget(order_id=order_id)
            user = await sync_to_async(lambda: order.user)()
            
            await models.ConfirmedOrder.objects.filter(order_id=order_id).adelete()

            logger.info(f"[PTB] Order [id: {order.order_id}] from user [{user}] canceled")

            text_to_user = (
                f"🔔 ваш заказ *№{order.order_id}*   ❌  отменён\n\n"
                f"_товары в заказе:_\n"
            )

            for part_id in order.parts:
                count = order.parts[part_id]['count']
                price = order.parts[part_id]['price']
                name = order.parts[part_id]['name']

                part = await models.Part.objects.aget(part_id=part_id)
                await models.Part.objects.filter(part_id=part_id).aupdate(available_count=part.available_count+count, is_available=True)

                cost = round(count * price, 2)

                text_to_user += (
                    f"● *{name}*\n"
                    f"{count}шт. x {price}р.= _{cost}р._\n"
                )

            text_to_user += f"\n💵 стоимость: _{order.cost}р._"

            await context.bot.send_message(
                chat_id=user.user_id,
                text=text_to_user,
                parse_mode=ParseMode.MARKDOWN,
            )
        except:
            order = None

    if callback == str(all_confirmed_order_states["ACCEPT_ORDER"]):
        try:
            order = await models.ConfirmedOrder.objects.aget(order_id=order_id)
            user = await sync_to_async(lambda: order.user)()

            order.is_accepted = True
            order.accepted_time = datetime.now(timezone.utc)
            
            await models.ConfirmedOrder.objects.filter(order_id=order_id).aupdate(
                is_accepted = order.is_accepted,
                accepted_time = order.accepted_time
            )

            logger.info(f"[PTB] Order [id: {order.order_id}] from user [{user}] applied")

            text_to_user = f"🔔 ваш заказ *№{order.order_id}*   📥  принят"

            await context.bot.send_message(
                chat_id=user.user_id,
                text=text_to_user,
                parse_mode=ParseMode.MARKDOWN,
            )
        except:
            order = None

    if callback == str(all_confirmed_order_states["COMPLETE_ORDER"]):
        try:
            order = await models.ConfirmedOrder.objects.aget(order_id=order_id)
            user = await sync_to_async(lambda: order.user)()
            
            await models.CompletedOrder.objects.acreate(
                order_id = order.order_id,
                user = user,
                parts = order.parts,
                cost = order.cost,
                ordered_time = order.ordered_time,
                accepted_time = order.accepted_time,
                completed_time = datetime.now(timezone.utc)
            )

            await models.ConfirmedOrder.objects.filter(order_id=order_id).adelete()

            logger.info(f"[PTB] Order [id: {order.order_id}] from user [{user}] completed")

            text_to_user = f"🔔 ваш заказ *№{order.order_id}*   ✅  завершён"

            await context.bot.send_message(
                chat_id=user.user_id,
                text=text_to_user,
                parse_mode=ParseMode.MARKDOWN,
            )
        except:
            order = None

    if order:
        ordered_time = order.ordered_time + CONFIG.TZ_OFFSET
        accepted_time = order.accepted_time + CONFIG.TZ_OFFSET

        order_user = await sync_to_async(lambda: order.user)()

        text += (
            f"- заказ *№{order.order_id}* -\n"
            f"- от {order_user.username} -\n\n"
            f"👤 *на имя*: _{order_user.name}_\n"
            f"📞 *телефон*: _+375{order_user.phone_number}_\n"
            f"📍 *адрес*: _{order_user.delivery_address}_\n\n"
            f"*оформлен*: _{ordered_time.strftime('%d.%m.%Y %H:%M')}_\n"
        )

        if order.is_accepted:
            text += f"*принят*: ✅ _{accepted_time.strftime('%d.%m.%Y %H:%M')}_\n\n"
        else:
            text += f"*требует подтверждения* ❌\n\n"

        for part_id in order.parts:
            count = order.parts[part_id]['count']
            price = order.parts[part_id]['price']
            name = order.parts[part_id]['name']

            cost = round(count * price, 2)

            text += (
                f"● *{name}*, id: *{part_id}*\n"
                f"{count}шт. x {price}р.= _{cost}р._\n"
            )

        text += f"\n💵 стоимость: _{order.cost}р._\n\n"

        if callback == str(all_confirmed_order_states["CANCEL_ORDER"]):
            text += f"🗑 *заказ отменён и удалён у пользователя*"

            keyboard = [
                [InlineKeyboardButton("↩️ назад", callback_data=str(admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]))]
            ]

        elif callback == str(all_confirmed_order_states["COMPLETE_ORDER"]):
            text += f"✅ *заказ завершён*"

            keyboard = [
                [InlineKeyboardButton("↩️ назад", callback_data=str(admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]))]
            ]

        elif order.is_accepted:
            keyboard = [
                [
                    InlineKeyboardButton("⬅️", callback_data=str(all_confirmed_order_states["PREVIOUS"])),
                    InlineKeyboardButton("➡️", callback_data=str(all_confirmed_order_states["NEXT"])),
                ],
                [
                    InlineKeyboardButton("✅ завершить", callback_data=str(all_confirmed_order_states["COMPLETE_ORDER"]))
                ],
                [
                    InlineKeyboardButton("❌ отменить", callback_data=str(all_confirmed_order_states["CANCEL_ORDER"]))
                ],
                [
                    InlineKeyboardButton("↩️ назад", callback_data=str(top_states["ADMIN_PANEL"]))
                ]
            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("⬅️", callback_data=str(all_confirmed_order_states["PREVIOUS"])),
                    InlineKeyboardButton("➡️", callback_data=str(all_confirmed_order_states["NEXT"])),
                ],
                [
                    InlineKeyboardButton("📥 принять", callback_data=str(all_confirmed_order_states["ACCEPT_ORDER"]))
                ],
                [
                    InlineKeyboardButton("❌ отменить", callback_data=str(all_confirmed_order_states["CANCEL_ORDER"]))
                ],
                [
                    InlineKeyboardButton("↩️ назад", callback_data=str(top_states["ADMIN_PANEL"]))
                ]
            ]

    else:
        text += CONFIG.EMPTY_TEXT

        keyboard = [
            [InlineKeyboardButton("↩️ назад", callback_data=str(top_states["ADMIN_PANEL"]))]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if callback == str(admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]):
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=f"{URL}/static/img/bot/malarka_shop_bot_all_confirmed_orders.jpg?a={CONFIG.TIMESTAMP_START}",
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
    
    return admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]


async def confirmed_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List of user's confirmed orders"""

    query = update.callback_query
    callback = query.data
    await query.answer()

    order = None
    order_id = context.user_data.get("confirmed_order_id")
    
    user_id = context.user_data.get("user_id")
    user = await models.User.objects.aget(user_id=user_id)

    text = (
        f"*[🕓 ваши заказы]*\n\n\n"
    )

    if callback == str(top_states["CONFIRMED_ORDER_LIST"]):
        order = await models.ConfirmedOrder.objects.filter(user=user).afirst()
        if order:
            order_id = order.order_id

        context.user_data["confirmed_order_id"] = order_id

    if callback == str(confirmed_order_states["PREVIOUS"]):
        order = await models.ConfirmedOrder.objects.filter(Q(user=user) & Q(order_id__lt=order_id)).alast()
        if not order:
            order = await models.ConfirmedOrder.objects.filter(user=user).alast()
        if order:
            context.user_data["confirmed_order_id"] = order.order_id

    if callback == str(confirmed_order_states["NEXT"]):
        order = await models.ConfirmedOrder.objects.filter(Q(user=user) & Q(order_id__gt=order_id)).afirst()
        if not order:
            order = await models.ConfirmedOrder.objects.filter(user=user).afirst()
        if order:
            context.user_data["confirmed_order_id"] = order.order_id

    if order:
        ordered_time = order.ordered_time + CONFIG.TZ_OFFSET
        accepted_time = order.accepted_time + CONFIG.TZ_OFFSET

        text += (
            f"- заказ *№{order.order_id}* -\n\n"
            f"оформлен: _{ordered_time.strftime('%d.%m.%Y %H:%M')}_\n"
        )

        if order.is_accepted:
            text += f"принят: ✅ _{accepted_time.strftime('%d.%m.%Y %H:%M')}_\n\n"
        else:
            text += f"принят: 🕓 _в обработке_\n\n"

        for part_id in order.parts:
            count = order.parts[part_id]['count']
            price = order.parts[part_id]['price']
            name = order.parts[part_id]['name']

            cost = round(count * price, 2)

            text += (
                f"● *{name}*\n"
                f"{count}шт. x {price}р.= _{cost}р._\n"
            )

        text += f"\n💵 стоимость: _{order.cost}р._"

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
                media=f"{URL}/static/img/bot/malarka_shop_bot_confirmed_orders.jpg?a={CONFIG.TIMESTAMP_START}",
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

    text = (
        f"*[✅ архив заказов]*\n\n\n"
    )

    if callback == str(top_states["COMPLETED_ORDER_LIST"]):
        order = await models.CompletedOrder.objects.filter(user=user).afirst()
        if order:
            order_id = order.order_id

        context.user_data["completed_order_id"] = order_id

    if callback == str(completed_order_states["PREVIOUS"]):
        order = await models.CompletedOrder.objects.filter(Q(user=user) & Q(order_id__lt=order_id)).alast()
        if not order:
            order = await models.CompletedOrder.objects.filter(user=user).alast()
        if order:
            context.user_data["completed_order_id"] = order.order_id

    if callback == str(completed_order_states["NEXT"]):
        order = await models.CompletedOrder.objects.filter(Q(user=user) & Q(order_id__gt=order_id)).afirst()
        if not order:
            order = await models.CompletedOrder.objects.filter(user=user).afirst()
        if order:
            context.user_data["completed_order_id"] = order.order_id

    if order:
        ordered_time = order.ordered_time + CONFIG.TZ_OFFSET
        accepted_time = order.accepted_time + CONFIG.TZ_OFFSET
        completed_time = order.completed_time + CONFIG.TZ_OFFSET

        text += (
            f"- заказ *№{order.order_id}* -\n\n"
            f"оформлен: _{ordered_time.strftime('%d.%m.%Y %H:%M')}_\n"
            f"принят: _{accepted_time.strftime('%d.%m.%Y %H:%M')}_\n"
            f"завершён: _{completed_time.strftime('%d.%m.%Y %H:%M')}_\n\n"
        )

        for part_id in order.parts:
            count = order.parts[part_id]['count']
            price = order.parts[part_id]['price']
            name = order.parts[part_id]['name']

            cost = round(count * price, 2)

            text += (
                f"● *{name}*\n"
                f"{count}шт. x {price}р.= _{cost}р._\n"
            )

        text += f"\n💵 стоимость: _{order.cost}р._"

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
                media=f"{URL}/static/img/bot/malarka_shop_bot_completed_orders.jpg?a={CONFIG.TIMESTAMP_START}",
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

    text = (
        f"\n_выберите категорию товара ниже:_"
    )

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
            media=f"{URL}/static/img/bot/malarka_shop_bot_in_catalog.jpg?a={CONFIG.TIMESTAMP_START}",
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
            media=f"{URL}/static/img/bot/malarka_shop_bot_in_catalog.jpg?a={CONFIG.TIMESTAMP_START}",
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
            category = callback.split(SPLIT, 1)[1]
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
        part = await models.Part.objects.filter(Q(is_available=True) & Q(available_count__gt=0) & Q(category=category)).afirst()

        if not part:
            await empty_category(update, context)
            return top_states["EMPTY_CATEGORY"]

        part_id = part.part_id
        
        context.user_data["part_id"] = part_id

        if str(part_id) in order.parts:
            # if part.available_count == 0:
            #     part_deleted_from_catalog = True
            #     order.parts.pop(str(part_id))
            #     await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts) elif
            if order.parts[str(part_id)]['count'] > part.available_count:
                order.parts[str(part_id)]['count'] = part.available_count
                part_not_enough_available_count = True
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)

    if callback == str(product_card_states["PREVIOUS"]):
        part = await models.Part.objects.filter(Q(is_available=True) & Q(available_count__gt=0) & Q(category=category) & Q(part_id__lt=part_id)).alast()

        if not part:
            part = await models.Part.objects.filter(Q(is_available=True) & Q(available_count__gt=0) & Q(category=category)).alast()

        if part:
            context.user_data["part_id"] = part.part_id

            if str(part.part_id) in order.parts:
                # if part.available_count == 0:
                #     part_deleted_from_catalog = True
                #     order.parts.pop(str(part_id))
                #     await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
                if order.parts[str(part.part_id)]['count'] > part.available_count:
                    order.parts[str(part.part_id)]['count'] = part.available_count
                    part_not_enough_available_count = True
                    await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
        else:
            await empty_category(update, context)
            return top_states["EMPTY_CATEGORY"]
  
    if callback == str(product_card_states["NEXT"]):
        part = await models.Part.objects.filter(Q(is_available=True) & Q(available_count__gt=0) & Q(category=category) & Q(part_id__gt=part_id)).afirst()

        if not part:
            part = await models.Part.objects.filter(Q(is_available=True) & Q(available_count__gt=0) & Q(category=category)).afirst()

        if part:
            context.user_data["part_id"] = part.part_id

            if str(part.part_id) in order.parts:
                # if part.available_count == 0:
                #     part_deleted_from_catalog = True
                #     order.parts.pop(str(part_id))
                #     await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
                if order.parts[str(part.part_id)]['count'] > part.available_count:
                    order.parts[str(part.part_id)]['count'] = part.available_count
                    part_not_enough_available_count = True
                    await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
        else:
            await empty_category(update, context)
            return top_states["EMPTY_CATEGORY"]

    if callback == str(product_card_states["REMOVE"]):
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False or part.available_count == 0:
            part_deleted_from_catalog = True
            if str(part_id) in order.parts:
                order.parts.pop(str(part_id))
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
        elif str(part_id) in order.parts:
            if order.parts[str(part_id)]['count'] - 1 > part.available_count:
                order.parts[str(part_id)]['count'] = part.available_count
                part_not_enough_available_count = True
            elif order.parts[str(part_id)]['count'] > 1:
                order.parts[str(part_id)]['count'] -= 1
            else:
                order.parts.pop(str(part_id))
            await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)

    if callback == str(product_card_states["ADD"]):
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False or part.available_count == 0:
            part_deleted_from_catalog = True
            if str(part_id) in order.parts:
                order.parts.pop(str(part_id))
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
        else:
            if str(part_id) in order.parts:
                if order.parts[str(part_id)]['count'] + 1 <= part.available_count:
                    order.parts[str(part_id)]['count'] += 1
                else:
                    order.parts[str(part_id)]['count'] = part.available_count
                    part_not_enough_available_count = True
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
            elif part.available_count > 0:
                order.parts[str(part_id)] = {
                    'name': part.name,
                    'category': part.category,
                    'description': part.description,
                    'price': part.price,
                    'count': 1,
                    'image': part.image.url
                }
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
            else:
                part_not_enough_available_count = True 

    if entered_part_count is not None:
        await delete_last_msg(update)
        part = await models.Part.objects.aget(part_id=part_id)
        if part.is_available == False or part.available_count == 0:
            part_deleted_from_catalog = True
            if str(part_id) in order.parts:
                order.parts.pop(str(part_id))
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)
        elif entered_part_count > 0:
            if entered_part_count <= part.available_count:
                order.parts[str(part_id)] = {
                    'name': part.name,
                    'category': part.category,
                    'description': part.description,
                    'price': part.price,
                    'count': entered_part_count,
                    'image': part.image.url
                }
            else:
                order.parts[str(part_id)] = {
                    'name': part.name,
                    'category': part.category,
                    'description': part.description,
                    'price': part.price,
                    'count': part.available_count,
                    'image': part.image.url
                }
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
        count = order.parts[str(part.part_id)]['count']
        cost = round(count * part.price, 2)
        text += (
            f"\nв корзине: *{count}шт.*\n"
            f"на *{cost}р.*\n"
        )

    if part_deleted_from_catalog:
        text += (
            f"\n⚠️ *произошла ошибка*\n"
            f"_товар только что был убран из каталога_\n"
            f"_чтобы продолжить, выберите другой товар_\n"
        )

    if part_not_enough_available_count:
        text += (
            f"\n⚠️ *произошла ошибка*\n"
            f"_выставлено максимально доступное количество товара, либо товар убран из корзины_\n"
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
            chat_id=context.user_data.get("user_id"),
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

    text = (
        f"введите количество товара, которое хотите добавить в корзину\n\n"
        f"*0* - _удалить из корзины_"
    )
    
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
        user = user,
        parts = order.parts,
        cost = order.cost,
        ordered_time = datetime.now(timezone.utc)
    )

    parts = models.Part.objects.filter(part_id__in=list(map(int, order.parts.keys())))

    async for part in parts:
        count = part.available_count - order.parts[str(part.part_id)]['count']
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
    
    text_to_admin = (
        f"🔔 поступил заказ *№{order.order_id}* от {user.username}\n\n"
        f"👤 *на имя*: {user.name}\n"
        f"📞 *телефон*: +375{user.phone_number}\n"
        f"📍 *адрес*: {user.delivery_address}\n\n"
        f"_товары в заказе:_\n"
    )

    for part_id in order.parts:
        count = order.parts[part_id]['count']
        price = order.parts[part_id]['price']
        name = order.parts[part_id]['name']

        cost = round(count * price, 2)

        text_to_admin += (
            f"● *{name}*, id: *{part_id}*\n"
            f"{count}шт. x {price}р.= _{cost}р._\n"
        )

    text_to_admin += f"\n💵 стоимость: _{order.cost}р._"
    
    admins_with_notifications_enabled = models.Admin.objects.filter(is_notification_enabled=True)

    async for admin in admins_with_notifications_enabled:
        await context.bot.send_message(
            chat_id=admin.admin_id,
            text=text_to_admin,
            parse_mode=ParseMode.MARKDOWN,
        )
    
    logger.info(f"[PTB] Order [id: {order.order_id}] from user [{user}] confirmed")


async def into_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cart"""

    query = update.callback_query
    callback = query.data
    await query.answer()
    
    order_id = context.user_data.get("order_id")
    order = await models.Order.objects.aget(order_id=order_id)
    order.cost = 0

    user = await models.User.objects.aget(user_id=context.user_data.get("user_id"))

    text = (
        f"*[ 🛒 корзина ]*\n\n\n"
    )
    reply_markup = None

    if bool(order.parts):
        text += (
            f"_ваши товары в корзине:_\n\n"
        )

        parts = models.Part.objects.filter(part_id__in=list(map(int, order.parts.keys())))

        if callback == str(top_states["INTO_CART"]):
            async for part in parts:
                count = order.parts[str(part.part_id)]['count']
                price = part.price
                cost = round(count * price, 2)
                order.cost += cost

                text += (
                    f"● *{part.name}*\n"
                    f"{count}шт. x {price}р.= _{cost}р._\n"
                )

            text += (
                f"\n💵 *итого:* _{order.cost}р._\n"
            )

            text += (
                f"\n_данные для доставки_\n"
                f"👤 *ваше имя*: _{user.name}_\n"
                f"📞 *телефон*: _+375{user.phone_number}_\n"
                f"📍 *адрес доставки*: _{user.delivery_address}_\n"
                f"(при необходимости можно изменить в профиле)\n"
            )

            keyboard = [
                [
                    InlineKeyboardButton("📦 оформить заказ", callback_data=str(into_cart_states["MAKE_ORDER"]))
                ],
                [
                    InlineKeyboardButton("🗑 очистить корзину", callback_data=str(into_cart_states["EMPTY_CART"]))
                ],
                [
                    InlineKeyboardButton("↩️ в начало", callback_data=str(top_states["START"]))
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

        if callback == str(into_cart_states["MAKE_ORDER"]):
            async for part in parts:
                count = order.parts[str(part.part_id)]['count']
                price = part.price
                cost = round(count * price, 2)
                order.cost += cost

                text += (
                    f"● *{part.name}*\n"
                    f"{count}шт. x {price}р.= _{cost}р._\n"
                )

            text += (
                f"\n💵 *итого:* _{order.cost}р._\n"
            )

            text += (
                f"\n_данные для доставки_\n"
                f"👤 *ваше имя*: _{user.name}_\n"
                f"📞 *телефон*: _+375{user.phone_number}_\n"
                f"📍 *адрес доставки*: _{user.delivery_address}_\n"
                f"(при необходимости можно изменить в профиле)\n"
            )

            text += (
                f"\n❔ *подтверждение заказа*. _вы уверены_?"
            )

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
                part_id = str(part.part_id)

                if part.is_available == False or part.available_count == 0:
                    text += (
                        f"● *{part.name}*\n"
                        f"{order.parts[part_id]['count']}шт.\n"
                        f"_[удалено из каталога]_,\n"
                    )

                    parts_id_deleted_from_catalog.append(part_id)
                    order.parts.pop(part_id)
                else:
                    order.parts[part_id]['name'] = part.name
                    order.parts[part_id]['category'] = part.category
                    order.parts[part_id]['description'] = part.description
                    order.parts[part_id]['price'] = part.price
                    count = order.parts[part_id]['count']
                    order.parts[part_id]['image'] = part.image.url

                    cost = round(count * part.price, 2)

                    if count > part.available_count:
                        text += (
                            f"● *{part.name}*\n"
                            f"{part.available_count}шт. x {part.price}р.= _{cost}р._\n"
                            f"_[выст. макс. дост. кол-во]_,\n"
                        )

                        order.parts[part_id]['count'] = part.available_count
                        parts_id_not_enough_available_count.append(part_id)
                    else:
                        text += (
                            f"● *{part.name}*\n"
                            f"{count}шт. x {part.price}р.= _{cost}р._\n"
                        )
                        order.cost += cost

            text += (
                f"\n💵 *итого:* _{order.cost}р._\n"
            )

            if len(parts_id_deleted_from_catalog) or len(parts_id_not_enough_available_count):   
                await models.Order.objects.filter(order_id=order_id).aupdate(parts=order.parts)

                keyboard = [
                    [
                        InlineKeyboardButton("✅ ок", callback_data=str(into_cart_states["MAKE_ORDER"]))
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                text += (
                    f"\n⚠️ *произошла ошибка*\n"
                    f"внимание, в корзине проведены изменения, продолжить?"
                )
            else:
                await confirm_order_to_db(update, context, order)
                return top_states["END"]

        if callback == str(into_cart_states["EMPTY_CART"]):

            await models.Order.objects.filter(order_id=order_id).aupdate(parts={})

            text += CONFIG.EMPTY_TEXT
            keyboard = [   
                [
                    InlineKeyboardButton("↩️ в начало", callback_data=str(top_states["START"]))
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

    else:
        text += CONFIG.EMPTY_TEXT
        keyboard = [   
            [
                InlineKeyboardButton("↩️ в начало", callback_data=str(top_states["START"]))
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

    if callback == str(top_states["INTO_CART"]):
        await query.edit_message_media(
                media=InputMediaPhoto(
                    media=f"{URL}/static/img/bot/malarka_shop_bot_cart.jpg?a={CONFIG.TIMESTAMP_START}",
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN,
                ),
                reply_markup=reply_markup
            )
    else:
        await query.edit_message_caption(
            caption=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    return top_states["INTO_CART"]


# Set up PTB application and a web application for handling the incoming requests.
context_types = ContextTypes(context=CallbackContext)
ptb_application = (
    Application.builder().token(TOKEN).updater(None).context_types(context_types).build()
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
                ),
                CallbackQueryHandler(
                    admin_panel, 
                    pattern="^" + str(top_states["ADMIN_PANEL"]) + "$"
                ),
                CallbackQueryHandler(
                    user_profile_edit, 
                    pattern="^" + str(top_states["USER_PROFILE_EDIT"]) + "$"
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
                    start, 
                    pattern="^" + str(top_states["START"]) + "$"
                )
            ],

            top_states["USER_PROFILE_EDIT"]: [
                CallbackQueryHandler(
                    start, 
                    pattern="^" + str(top_states["START"]) + "$"
                ),
                CallbackQueryHandler(
                    ask_for_enter_name,
                    pattern="^" + str(user_profile_edit_states["ENTER_NAME"]) + "$"
                ),
                CallbackQueryHandler(
                    ask_for_enter_phone_number,
                    pattern="^" + str(user_profile_edit_states["ENTER_PHONE_NUMBER"]) + "$"
                ),
                CallbackQueryHandler(
                    ask_for_enter_delivery_address,
                    pattern="^" + str(user_profile_edit_states["ENTER_DELIVERY_ADDRESS"]) + "$"
                )
            ],

            top_states["CHOOSE_CATEGORY"]: [
                CallbackQueryHandler(
                    start, 
                    pattern="^" + str(top_states["START"]) + "$"
                ),
                CallbackQueryHandler(
                    product_cards,
                    pattern="^" + str(top_states["PRODUCT_CARDS"]) + "_[a-zA-Z_]{1,64}$"
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
                ),
                CallbackQueryHandler(
                    into_cart,
                    pattern="^" + str(into_cart_states["EMPTY_CART"]) + "$"
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

            top_states["END"]: [],


            user_profile_edit_states["GET_NAME"]: [
                MessageHandler(filters.Regex(".{1,64}"), get_name),
                MessageHandler(~filters.Regex(".{1,64}"), delete_last_msg)
            ],
            user_profile_edit_states["GET_PHONE_NUMBER"]: [
                MessageHandler(filters.Regex("^[0-9]{9}$"), get_phone_number),
                MessageHandler(~filters.Regex("^[0-9]{9}$"), delete_last_msg)
            ],
            user_profile_edit_states["GET_DELIVERY_ADDRESS"]: [
                MessageHandler(filters.Regex(".{1,128}"), get_delivery_address),
                MessageHandler(~filters.Regex(".{1,128}"), delete_last_msg)
            ],

            
            admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]: [
                CallbackQueryHandler(
                    admin_panel, 
                    pattern="^" + str(top_states["ADMIN_PANEL"]) + "$"
                ),
                CallbackQueryHandler(
                    all_confirmed_order_list,
                    pattern="^" + str(admin_panel_states["ALL_CONFIRMED_ORDER_LIST"]) + "$"
                ),
                CallbackQueryHandler(
                    all_confirmed_order_list, 
                    pattern="^" + str(all_confirmed_order_states["PREVIOUS"]) + "$"
                ),
                CallbackQueryHandler(
                    all_confirmed_order_list, 
                    pattern="^" + str(all_confirmed_order_states["NEXT"]) + "$"
                ),
                CallbackQueryHandler(
                    all_confirmed_order_list, 
                    pattern="^" + str(all_confirmed_order_states["ACCEPT_ORDER"]) + "$"
                ),
                CallbackQueryHandler(
                    all_confirmed_order_list, 
                    pattern="^" + str(all_confirmed_order_states["COMPLETE_ORDER"]) + "$"
                ),
                CallbackQueryHandler(
                    all_confirmed_order_list, 
                    pattern="^" + str(all_confirmed_order_states["CANCEL_ORDER"]) + "$"
                )
            ],


            product_card_states["GET_PART_BY_ID"]: [
                MessageHandler(filters.Regex("^[0-9]{1,}$"), product_cards),
                MessageHandler(~filters.Regex("^[0-9]{1,}$"), delete_last_msg)
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
            port=PORT,
            use_colors=False,
            host="127.0.0.1",
        )
    )

    # Pass webhook settings to telegram
    await ptb_application.bot.set_webhook(url=f"{URL}/telegram", allowed_updates=Update.ALL_TYPES)

    # Run application and webserver together
    async with ptb_application:
        await ptb_application.start()
        await webserver.serve()
        await ptb_application.stop()

if __name__ == "__main__":
    asyncio.run(main())
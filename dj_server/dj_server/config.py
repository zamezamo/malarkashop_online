TITLE = 'AutoCustomersStore'
BOT_LINK="tg://resolve?domain=autocosmeticsstore_bot"

# Define bot configuration constants
URL = "https://2f80-178-124-178-90.ngrok-free.app"
ADMIN_CHAT_ID = 542399495 # @zamezamo
PORT = 8000
TOKEN = "7000362389:AAFGsZk51Japmkc_U6cXqmHM3IFOPo8eCI0"  # KEEP IT IN SECRET!

START_TEXT = (
    f"Добро пожаловать в *{TITLE}*!\n"
    f"Подписывайтесь на наш [канал]({BOT_LINK})!\n"
    f"\n"
    f"описание\nописание\nописание\nописание\n"
    f"\n"
)

START_TEXT_OVER = (
    f"*{TITLE}*\n"
    f"Подписывайтесь на наш [канал]({BOT_LINK})!\n"
    f"\n"
    f"описание\nописание\nописание\nописание\n"
    f"\n"
)

START_TEXT_PARTS_IN_CART = (
    f"\n_в корзине присутствуют товары_"
)

CHOOSE_CATEGORY_TEXT = (
    f"\n_выберите категорию товара ниже:_"
)

ENTER_PARTS_COUNT = (
    f"введи количество товара, которое хочешь добавить в корзину\n\n"
    f"0 - удалить из корзины"
)

CATEGORY_CHOICES = {
    "ABRSMATS": "абразивные материалы",
    "POLWHEEL": "полировальные круги",
    "PNTTAPES": "малярные ленты",
    "PLANES": "рубанки",
    "POLPASTS": "полировальные пасты",
    "SPRAYGUN": "краскопульты",
    "SUPPLIES": "расходные материалы",
    "OTHER": "другое"
}
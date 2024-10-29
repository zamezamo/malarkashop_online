TITLE = 'AutoCustomersStore'
BOT_LINK="tg://resolve?domain=autocosmeticsstore_bot"

# Define bot configuration constants
URL = "https://0524-2a09-bac5-506f-2dc-00-49-1e4.ngrok-free.app"
ADMIN_CHAT_ID = 542399495 # @zamezamo
PORT = 8000
TOKEN = "7000362389:AAFGsZk51Japmkc_U6cXqmHM3IFOPo8eCI0"  # KEEP IT IN SECRET!

START_TEXT = (
    f"Добро пожаловать в *{TITLE}*!\n"
    f"Подписывайтесь на наш [канал]({BOT_LINK})!\n"
    f"\n"
    f"описание\nописание\nописание\nописание\n"
    f"\n"
    f"Для того чтобы перейти в каталог нажмите _кнопку_ ниже\n"
)

CHOOSE_CATEGORY_TEXT = (
    f"\n_выберите категорию товара ниже:_"
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
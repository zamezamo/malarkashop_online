TITLE = 'AutoCustomersStore'
BOT_LINK="tg://resolve?domain=autocosmeticsstore_bot"

# Define bot configuration constants
URL = "https://83e1-178-124-178-90.ngrok-free.app"
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

CATEGORY_CHOICES = {
    "ABRAS_MATHERIALS": "абразивные материалы",
    "POLISHING_WHEELS": "полировальные круги",
    "PAINTING_TAPES": "малярные ленты",
    "PLANES": "рубанки",
    "POLISHING_PASTES": "полировальные пасты",
    "SPRAY_GUNS": "краскопульты",
    "SUPPLIES": "расходные материалы",
    "OTHER": "другое"
}
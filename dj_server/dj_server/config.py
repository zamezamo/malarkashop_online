import datetime

TZ_OFFSET = datetime.timedelta(hours=3)

TIMESTAMP_START = int(datetime.datetime.now().timestamp())

TITLE = 'MalarkaShop'
CHANNEL_LINK="tg://resolve?domain=malarkashop_bot"


""" CHOICES FOR CERTAIN PARTS CATEGORY """
"""         64 characters max          """

CATEGORY_CHOICES = {
    "abrasive_wheels": "🛠 абразивные круги",
    "abrasive_strips": "🛠 абразивные полоски",
    "trizact_velvet": "🛠 trizact - velvet",
    "washing_paper": "🛠 замывочная бумага",
    "scotch_and_masking_tapes": "🛠 скотчи, малярные ленты",
    "planes": "🛠 рубанки",
    "polishing_wheels": "🛠 полировальные круги",
    "supplies": "🛠 расходные материалы",
    "spray_guns": "🛠 краскопульты",
    "other": "🛠 другое",
    "preorder": "🛠 предзаказ"
}

DEFAULT_PART_IMAGE = "malarka_shop_bot_part_no_image.jpg"

EMPTY_TEXT = (
    f"здесь пусто.."
)
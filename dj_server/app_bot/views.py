import json

import dj_server.config as CONFIG

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render

from telegram import Update
from __main__ import ptb_application

# Create your views here
context = {'title': CONFIG.TITLE}
async def index(request: HttpRequest) -> HttpResponse:
    return render(request, 'app_bot/index.html', context)

async def telegram(request: HttpRequest) -> HttpResponse:
    """Handle incoming Telegram updates by putting them into the `update_queue`"""
    await ptb_application.update_queue.put(
        Update.de_json(data=json.loads(request.body), bot=ptb_application.bot)
    )
    return HttpResponse()

async def health(request: HttpRequest) -> HttpResponse:
    """For the health endpoint, reply with a simple plain text message."""
    return HttpResponse("The bot is still running fine :)")
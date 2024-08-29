from django.shortcuts import render
from dj_server.settings import TITLE

# Create your views here.

context = {'title': TITLE}
def index(request):
    return render(request, 'app_bot/index.html', context)
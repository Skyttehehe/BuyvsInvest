import json

from django.http import JsonResponse
from django.shortcuts import render

from . import engine


def index(request):
    return render(request, "calculator/index.html", {
        "defaults_json": json.dumps(engine.DEFAULTS),
    })


def api_calculate(request):
    params = engine.parse_params(request.GET)
    result = engine.simulate(params)
    return JsonResponse(result)

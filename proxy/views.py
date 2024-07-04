# proxy/views.py
import os
import asyncio
import json

from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


from livekit import api
from uuid import uuid4
from .room import Room

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# agents ref
# https://docs.livekit.io/agents/plugins/

@csrf_exempt
@require_http_methods(["POST"])
async def create_room(request):
    if request.method != 'POST':
        return HttpResponseBadRequest()

    try:
        lkapi = api.LiveKitAPI(os.getenv('LIVEKIT_URL'))

        body = json.loads(request.body)
        identity = body.get('identity')
        if not identity:
            return HttpResponseBadRequest("identity is required")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid json")
    finally:
        await lkapi.aclose()
    
    room_id = str(uuid4())

    logger.info(f"try to push room_id to queeu {room_id}")
    # todo start a room worker

    # potentially use an async worker to handle this
    room = Room(room_id)
    asyncio.ensure_future(room.go_live())

    # end start room worker
    logger.info(f"room_id {room_id} pushed to queue")

    token = api.AccessToken() \
        .with_identity(identity) \
        .with_name(str(room_id)) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_id,
            can_publish=True,
        ))

    logger.info("return token and room info")
    return JsonResponse({
        "room_id": room_id,
        "ws_url": os.getenv('LIVEKIT_URL'),
        "token": token.to_jwt()
    })

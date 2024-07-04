# proxy/management/commands/local_client.py

import asyncio
import json
import requests
from django.core.management.base import BaseCommand
from livekit import rtc

from proxy.utils import Player, MicrophoneStream

url = 'http://127.0.0.1:8000/create_room/'

class Command(BaseCommand):
    help = 'Request the async endpoint with a given identity'

    def add_arguments(self, parser):
        parser.add_argument(
            'identity',
            type=str,
            help='Identity to be sent in the POST request',
        )

    def handle(self, *args, **kwargs):
        identity = kwargs['identity']

        asyncio.run(self.run(identity))

    async def run(self, identity):
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps({'identity': identity})
        )

        if response.status_code == 200:
            print(f'Success: {response.json()}')
            token = response.json()['token']
            ws_url = response.json()['ws_url']
            event_loop = asyncio.get_event_loop()
            room = rtc.Room(event_loop)
            player = Player()

            @room.on("participant_connected")
            def on_participant_connected(participant):
                print(f"participant connected: {participant.identity}")

            @room.on("connected")
            def on_connected():
                print("connected to room")

            @room.on("track_published")
            def on_track_published(
                track: rtc.LocalTrack, publication: rtc.LocalTrackPublication
            ):
                print("track published: %s", publication.sid)

            @room.on("track_subscribed")
            def on_track_subscribed(
                track: rtc.Track,
                publication: rtc.RemoteTrackPublication,
                participant: rtc.RemoteParticipant,
            ):
                print(
                    f"track subscribed: {publication.sid} from {participant.identity}"
                )
                if track.kind == rtc.TrackKind.KIND_AUDIO:
                    audio_stream = rtc.AudioStream(track)
                    asyncio.ensure_future(player.play(audio_stream))

            await room.connect(ws_url, token)

            try:
                stream = MicrophoneStream()
                await stream.publish(room)

                await asyncio.sleep(5)
            except Exception as e:
                print(f"failed to connect to room: {e}")
            finally:
                print("disconnecting microphone")
                await stream.close()
                print("disconnecting player")
                player.close()
                print("bot disconnect from the room")
                await room.disconnect()

        else:
            print(f'Error: {response.status_code} - {response.text}')

import os
import asyncio 

from livekit import api, rtc
from .utils import FileStream, Recorder

from logging import getLogger
logger = getLogger(__name__)

class Room():
    def __init__(self, name):
        self.name = str(name)
        self.stream = FileStream('audio.wav')
        self.recorder = Recorder('output.wav')

    async def go_live(self):
        logger.info("start go live")
        local_stop_event = asyncio.Event()
        token = (
            api.AccessToken()
            .with_identity("murky-bot")
            .with_name(self.name)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=self.name,
                    can_publish=True,
                )
            )
            .to_jwt()
        )
        logger.info("backend token received!")

        # event_loop = asyncio.get_event_loop()
        room = rtc.Room()

        @room.on("disconnected")
        def on_disconnected():
            logger.info("disconnected")

        @room.on("participant_connected")
        def on_participant_connected(participant):
            logger.info(f"participant connected: {participant.identity}")

        @room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(
                "participant disconnected: %s %s", participant.sid, participant.identity
            )       

            logger.info("bot disconnect from the room")

            local_stop_event.set()

        @room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            logger.info(f"track subscribed: {publication.sid} from {participant.identity}")
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                audio_stream = rtc.AudioStream(track)
                asyncio.ensure_future(self.recorder.record(audio_stream))
        
        logger.info("backend connecting to the room")
        try:
            await room.connect(os.getenv("LIVEKIT_URL"), token)
            # todo probably need to check existing participants since the mobile can
            # join the room before the backend
        except Exception as e:
            logger.error("failed to connect to room: %s", e)
            return

        logger.info("bakcend conected to the room")

        # publish stream to room
        await self.stream.publish(room)
        # todo local participant to publish audio
        logger.info("wait the event to be set")
        await local_stop_event.wait()

        await self.stream.close()
        self.recorder.close()

        logger.info("leaving the room")
        await rtc.Room.disconnect(room)
        logger.info("room is disconnected")

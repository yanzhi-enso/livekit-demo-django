import asyncio
import queue
import pyaudio

from livekit import rtc
import numpy as np
from pydub import AudioSegment

SAMPLE_RATE = 48000
NUM_CHANNELS = 1

from logging import getLogger
logger = getLogger(__name__)

class SineWaveStream():
    def __init__(self):
        self.source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        self.track = rtc.LocalAudioTrack.create_audio_track(
            'SineWave', self.source
        )
        self.options = rtc.TrackPublishOptions()
        self.options.source = rtc.TrackSource.SOURCE_MICROPHONE

        self.is_streaming = False
        self.task = None
    
    async def publish(self, room):
        self.publication = await room.local_participant.publish_track(
            self.track, self.options
        )
        logger.info("published track: %s", self.publication.track.sid)

        self.task = asyncio.ensure_future(self.play())
    
    async def play(self):
        self.is_streaming = True

        # dummy input fraquency
        frequency = 440
        amplitude = 32767  # for 16-bit audio
        samples_per_channel = 480  # 10ms at 48kHz
        time = np.arange(samples_per_channel) / SAMPLE_RATE
        total_samples = 0
        audio_frame = rtc.AudioFrame.create(SAMPLE_RATE, NUM_CHANNELS, samples_per_channel)
        frame_buffer = np.frombuffer(audio_frame.data, dtype=np.int16)

        while self.is_streaming:
            time = (total_samples + np.arange(samples_per_channel)) / SAMPLE_RATE
            sine_wave = (amplitude * np.sin(2 * np.pi * frequency * time)).astype(np.int16)
            np.copyto(frame_buffer, sine_wave)
            await self.source.capture_frame(audio_frame)
            total_samples += samples_per_channel
    
    async def close(self):
        self.is_streaming = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("task cancelled")

class MicrophoneStream():
    def __init__(self):
        self.source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        self.track = rtc.LocalAudioTrack.create_audio_track(
            'Microphone', self.source
        )
        self.options = rtc.TrackPublishOptions()
        self.options.source = rtc.TrackSource.SOURCE_MICROPHONE

        self._p = pyaudio.PyAudio()
        self._stream = self._p.open(
            format=pyaudio.paInt16,
            channels=NUM_CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=int(SAMPLE_RATE * 0.1),
            stream_callback=self.copyAudioFrame,
        )

        self.is_streaming = False
        self.task = None
        self.frame_queue = asyncio.Queue()

    async def publish(self, room):
        self.publication = await room.local_participant.publish_track(
            self.track, self.options
        )
        logger.info("published track: %s", self.publication.track.sid)

        self.task = asyncio.ensure_future(self.play())

    def copyAudioFrame(self, in_data, frame_count, time_info, status):
        # audio_data = np.frombuffer(in_data, dtype=np.int16)
        # print("audio_data length: ", len(audio_data), "expected frame_count:", frame_count)
        frames = rtc.AudioFrame(
            data=in_data,
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            samples_per_channel=frame_count,
        )

        self.frame_queue.put_nowait(frames)

        return (in_data, pyaudio.paContinue)

    async def play(self):
        self._stream.start_stream()

        while True:
            try:
                frames = await self.frame_queue.get()
                await self.source.capture_frame(frames)
            except asyncio.CancelledError:
                print("play is cancelled")
                return

    async def close(self):
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            logger.info("task cancelled")

        self._stream.stop_stream()
        self._stream.close()
        self._p.terminate()

class FileStream():
    def __init__(self, file_path: str):
        self.source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        self.track = rtc.LocalAudioTrack.create_audio_track(
            'File', self.source
        )
        self.options = rtc.TrackPublishOptions()
        self.options.source = rtc.TrackSource.SOURCE_MICROPHONE

        self.is_streaming = False
        self.task = None

        # read a local audio file as the source of the audioSegment
        self.total_as = ( AudioSegment \
                            .from_file(file_path) \
                            .set_frame_rate(SAMPLE_RATE) \
                            .set_channels(NUM_CHANNELS) \
                            .set_sample_width(2)
                        )
        print("len of audio segment: ", len(self.total_as))
        print("total bytes: ", len(self.total_as.raw_data))
    
    async def publish(self, room):
        print("publishing file stream")
        self.publication = await room.local_participant.publish_track(
            self.track, self.options
        )
        logger.info("published track: %s", self.publication.track.sid)

        print("started task to play file stream")
        self.task = asyncio.ensure_future(self.play())
    
    async def play(self):
        print("playing file stream")
        self.is_streaming = True
        try:
            audio_frame = rtc.AudioFrame.create(SAMPLE_RATE, NUM_CHANNELS, 480)
            raw_data = np.frombuffer(self.total_as.raw_data, dtype=np.int16)
            frame_buffer = np.frombuffer(audio_frame.data, dtype=np.int16)

            while self.is_streaming:
                # repeatly play the audio file as long as the streaming flag is True
                for start_idx in range(0, len(raw_data), 480):
                    end_idx = min(start_idx+480, len(raw_data))
                    chunk_data = raw_data[start_idx:end_idx]
                    if (len(chunk_data) < 480):
                        # padding the end chunk if it's shorter than 480 samples
                        chunk_data = np.pad(
                            chunk_data,
                            (0, 480 - len(chunk_data)),
                            'constant',
                            constant_values=(0, 0)
                        )

                    np.copyto(frame_buffer, chunk_data)
                    await self.source.capture_frame(audio_frame)
        except asyncio.CancelledError:
            print("Cancelled")
        except Exception as e:
            print("Exception in play file stream: ", e)

    async def close(self):
        self.is_streaming = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("task cancelled")

class Player():
    def __init__(self, clip_duration: float = 0.01):
        self._p = pyaudio.PyAudio()
        self._stream = self._p.open(
            format=pyaudio.paInt16,
            channels=NUM_CHANNELS,
            rate=SAMPLE_RATE,
            output=True,
            frames_per_buffer=int(SAMPLE_RATE * clip_duration)
        )

        self.is_streaming = False
    
    async def play(self, rtcStream: rtc.AudioStream):
        self.is_streaming = True
        async for frame_event in rtcStream:
            if not self.is_streaming:
                return
            self._stream.write(frame_event.frame.data.tobytes())

    def close(self):
        self.is_streaming = False
        self._stream.stop_stream()
        self._stream.close()
        self._p.terminate()

class Recorder():
    def __init__(self, file_path: str):
        self.audio_bucket = AudioSegment.empty()

        self.is_recording = False
        self.task = None
        self.file_path = file_path

    async def record(self, rtcStream: rtc.AudioStream):
        self.is_recording = True
        async for frame_event in rtcStream:
            if not self.is_recording:
                return

            raw_data = frame_event.frame.data.tobytes()
            frame_segment = AudioSegment(
                raw_data,
                sample_width=2,
                frame_rate=SAMPLE_RATE,
                channels=NUM_CHANNELS
            )
            self.audio_bucket += frame_segment

    def close(self):
        self.is_recording = False

        self.audio_bucket.export(self.file_path, format='wav')
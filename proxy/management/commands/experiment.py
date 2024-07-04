
from django.core.management.base import BaseCommand
import numpy as np
from pydub import AudioSegment
import pyaudio

SAMPLE_RATE = 48000

class Command(BaseCommand):
    help = 'experiment command'

    def handle(self, *args, **kwargs):
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=int(SAMPLE_RATE * 0.01)
        )

        audio_segment = AudioSegment.empty()

        stream.start_stream()

        for i in range(500):
            # roughly 5 seconds of audio
            data = stream.read(480, exception_on_overflow = False)
            chunk = AudioSegment(data, sample_width=2, frame_rate=SAMPLE_RATE, channels=1)
            audio_segment += chunk

        stream.stop_stream()
        stream.close()
        p.terminate()

        audio_segment.export('output_test.wav', format='wav')
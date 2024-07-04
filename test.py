import asyncio

from pydub import AudioSegment
import pyaudio

SAMPLE_RATE = 48000

def recorder():
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

async def blocking_task(queue):
    while True:
        try:
            print("waiting for task")
            obj = await queue.get()
        except asyncio.CancelledError:
            print("task cancelled")
            return

async def async_exp():
    q = asyncio.Queue()
    task = asyncio.ensure_future(blocking_task(q))

    await asyncio.sleep(2)

    print("stopping task")
    task.cancel()
    await task
    print("asyncio exited")

def exp():
    asyncio.run(async_exp())

if __name__ == '__main__':
    # recorder()
    exp()
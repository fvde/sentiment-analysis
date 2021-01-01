import asyncio

# This example uses the sounddevice library to get an audio stream from the
# microphone. It's not a dependency of the project but can be installed with
# `pip install sounddevice`.
import sounddevice


from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

import boto3
import json


"""
Here's an example of a custom event handler you can extend to
process the returned transcription results as needed. This
handler will simply print the text out to your interpreter.
"""

SENTIMENTS = {}
SENTIMENTS["POSITIVE"] = 0
SENTIMENTS["NEUTRAL"] = 0
SENTIMENTS["MIXED"] = 0
SENTIMENTS["NEGATIVE"] = 0


class MyEventHandler(TranscriptResultStreamHandler):
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        # This handler can be implemented to handle transcriptions as needed.
        # Here's an example to get started.
        results = transcript_event.transcript.results
        for result in results:
            # print(result)
            for alt in result.alternatives:
                comprehend = boto3.client(
                    service_name="comprehend", region_name="eu-central-1"
                )
                text = alt.transcript
                sentiment = comprehend.detect_sentiment(Text=text, LanguageCode="de")

                print(
                    "[Text] "
                    + text
                    + " [Sentiment] "
                    + str(sentiment["Sentiment"])
                    + " [Score] "
                    + str(sentiment["SentimentScore"])
                )

                SENTIMENTS[sentiment["Sentiment"]] += 1
                print(SENTIMENTS)
                break


async def mic_stream():
    # This function wraps the raw input stream from the microphone forwarding
    # the blocks to an asyncio.Queue.
    loop = asyncio.get_event_loop()
    input_queue = asyncio.Queue()

    def callback(indata, frame_count, time_info, status):
        loop.call_soon_threadsafe(input_queue.put_nowait, (bytes(indata), status))

    # Be sure to use the correct parameters for the audio stream that matches
    # the audio formats described for the source language you'll be using:
    # https://docs.aws.amazon.com/transcribe/latest/dg/streaming.html
    stream = sounddevice.RawInputStream(
        channels=1,
        samplerate=16000,
        callback=callback,
        blocksize=1024 * 2,
        dtype="int16",
    )
    # Initiate the audio stream and asynchronously yield the audio chunks
    # as they become available.
    with stream:
        while True:
            indata, status = await input_queue.get()
            yield indata, status


async def write_chunks(stream):
    # This connects the raw audio chunks generator coming from the microphone
    # and passes them along to the transcription stream.
    async for chunk, status in mic_stream():
        await stream.input_stream.send_audio_event(audio_chunk=chunk)
    await stream.input_stream.end_stream()


async def basic_transcribe():
    # Setup up our client with our chosen AWS region
    client = TranscribeStreamingClient(region="eu-central-1")

    # Start transcription to generate our async stream
    stream = await client.start_stream_transcription(
        language_code="de-DE",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )

    # Instantiate our handler and start processing events
    handler = MyEventHandler(stream.output_stream)
    await asyncio.gather(write_chunks(stream), handler.handle_events())


loop = asyncio.get_event_loop()
loop.run_until_complete(basic_transcribe())
loop.close()
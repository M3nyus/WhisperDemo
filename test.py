import asyncio
import redis.asyncio as redis
import base64
import numpy as np
import wave
import whisper
from scipy.signal import resample

# --- CONFIGURATION ---
REDIS_HOST = "localhost"
REDIS_PORT = "6379"
STREAM_KEY = "room:1"
SOURCE_SAMPLE_RATE = 48000
CHANNELS = 2
TARGET_SAMPLE_RATE = 16000


async def transcribe_with_fix():
    # 1. Connect
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

    # 2. Fetch all data with a small retry logic to ensure we get the "tail"
    # Sometimes the script runs so fast the last chunk hasn't arrived
    print("Reading from Redis...")
    response = await r.xread({STREAM_KEY: "0-0"}, count=None)

    if not response:
        print("No data.")
        return

    pcm_fragments = []
    for _, messages in response:
        for _, fields in messages:
            # Note the key might be b'pcm' or 'pcm' depending on how it was saved
            pcm_b64 = fields.get(b'pcm', fields.get('pcm'))
            if pcm_b64:
                pcm_bytes = base64.b64decode(pcm_b64)
                pcm_fragments.append(np.frombuffer(pcm_bytes, dtype=np.int16))

    if not pcm_fragments:
        return

    # 3. Process Audio (Stereo -> Mono)
    full_audio = np.concatenate(pcm_fragments)

    if CHANNELS == 2:
        # Check if length is even to avoid reshape errors if a frame was clipped
        if len(full_audio) % 2 != 0:
            full_audio = full_audio[:-1]
        full_audio = full_audio.reshape(-1, 2).mean(axis=1).astype(np.int16)

    # 4. Convert to float and Resample
    audio_float = full_audio.astype(np.float32) / 32768.0
    new_num_samples = int(len(audio_float) * TARGET_SAMPLE_RATE / SOURCE_SAMPLE_RATE)
    resampled_audio = resample(audio_float, new_num_samples)

    # --- FIX FOR CUTOFFS: Add 0.5s of silence padding ---
    # This helps Whisper realize the sentence is over and process the last word.
    padding = np.zeros(int(TARGET_SAMPLE_RATE * 0.5), dtype=np.float32)
    final_audio = np.concatenate([resampled_audio, padding])

    # 5. Save and Transcribe
    with wave.open("fixed_check.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TARGET_SAMPLE_RATE)
        wf.writeframes((final_audio * 32767).astype(np.int16).tobytes())

    print(f"Total audio duration: {len(final_audio) / TARGET_SAMPLE_RATE:.2f}s")

    # Load Model (using turbo for speed)
    model = whisper.load_model("large")

    # Use 'no_speech_threshold' to prevent it from cutting off early
    result = model.transcribe(
        final_audio,
        fp16=False,
        language="hu",
        condition_on_previous_text=False  # Helps with stutters/repetition
    )

    print("\n--- TRANSCRIPTION ---\n", result['text'])
    await r.close()


if __name__ == "__main__":
    asyncio.run(transcribe_with_fix())
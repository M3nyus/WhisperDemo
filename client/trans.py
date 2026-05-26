import redis
import base64
import numpy as np
#import resample
import whisper
from scipy.signal import resample
import os
from dotenv import load_dotenv
from Logger import Logger


#LOAD .ENV
load_dotenv()

#LOGGER
LOGFILE = os.getenv("TRANS_LOG")
log = Logger(LOGFILE)

# --- CONFIGURATION ---
ROOM_ID = "room"
CHUNK_INDEX = "0"
SOURCE_SAMPLE_RATE = 48000  # Default for WebRTC (aiortc/browser)
TARGET_SAMPLE_RATE = 16000  # Required by Whisper
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
WHISPER_MODEL = os.getenv("WHISPER_MODEL")


def transcribe_from_redis_stream(room_id, chunk_index):
    # Connect to Redis (decode_responses=True helps with the dictionary keys)
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    log.Logging(f"Redis connected. HOST={REDIS_HOST}, PORT={REDIS_PORT}")

    # Load the Turbo model (v3-turbo is very fast for live-ish data)
    model = whisper.load_model(WHISPER_MODEL)
    log.Logging(f"Redis model loaded: {WHISPER_MODEL}")

    stream_key = f"{room_id}:{chunk_index}"
    log.Logging(f"Stream key: {stream_key}")

    # 1. Read the stream from the beginning (0-0)
    data = r.xread({stream_key: "0-0"}, count=None)

    if not data:
        print(f"No data found in stream: {stream_key}")
        log.Logging("No data found in stream")
        return None

    all_audio_fragments = []

    # 2. Extract and decode PCM data
    # data format: [[stream_name, [(msg_id, {pcm: base64_str})]]]
    messages = data[0][1]
    for _, content in messages:
        # Decode Base64 string back to binary bytes
        pcm_bytes = base64.b64decode(content['pcm'])

        # WebRTC Mono is usually 16-bit signed integer (int16)
        audio_fragment = np.frombuffer(pcm_bytes, dtype=np.int16)
        all_audio_fragments.append(audio_fragment)

    if not all_audio_fragments:
        return None

    # 3. Combine and Normalize to float32 [-1.0, 1.0]
    full_audio = np.concatenate(all_audio_fragments).astype(np.float32) / 32768.0

    # 4. Resample if necessary
    # If your source is not 16k, we must resample it
    if SOURCE_SAMPLE_RATE != TARGET_SAMPLE_RATE:
        num_samples = int(len(full_audio) * TARGET_SAMPLE_RATE / SOURCE_SAMPLE_RATE)
        full_audio = resample(full_audio, num_samples)

    # 5. Whisper Inference
    print(f"Processing {len(full_audio) / TARGET_SAMPLE_RATE:.2f}s of audio at {TARGET_SAMPLE_RATE}Hz...")
    log.Logging(f"Processing {len(full_audio) / TARGET_SAMPLE_RATE:.2f}s of audio at {TARGET_SAMPLE_RATE}Hz...")

    # language="hu" (example for Hungarian) or "en" (English)
    # Use fp16=True ONLY if you have a modern NVIDIA GPU
    result = model.transcribe(full_audio, fp16=False, language="hu")

    log.Logging(f"Transcription done.")
    return result['text']


if __name__ == "__main__":
    text = transcribe_from_redis_stream(ROOM_ID, CHUNK_INDEX)
    if text:
        print(f"--- TRANSCRIPTION ---\n{text}")
        log.Logging("--- TRANSCRIPTION ---")
    else:
        print("Transcription failed or no data available.")
        log.Logging("Transcription failed or no data available.")
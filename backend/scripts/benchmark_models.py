#!/usr/bin/env python3
"""
Benchmark Whisper Models for TheWallflower.

This script allows you to evaluate the accuracy (WER) and speed of the currently
running Whisper model using a set of test audio files.

Usage:
    python3 benchmark_models.py --input <directory_with_wavs> --host <whisper_host> --port <whisper_port>

Directory Structure:
    The input directory should contain pairs of files:
    - audio1.wav  (16kHz, Mono, 32-bit Float or 16-bit PCM)
    - audio1.txt  (Ground truth transcript)

Dependencies:
    pip install websockets numpy jiwer soundfile
"""

import asyncio
import argparse
import json
import os
import time
import logging
import numpy as np
import websockets
import soundfile as sf
import jiwer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants matching production worker.py
SAMPLE_RATE = 16000
CHUNK_SIZE = 4096 # Send in smaller chunks for smoother streaming simulation

async def transcribe_file(filepath, host, port):
    """Transcribe a single audio file using the WhisperLive server."""
    uri = f"ws://{host}:{port}"
    logger.info(f"Connecting to {uri}...")

    audio_data, samplerate = sf.read(filepath, dtype='float32')
    
    # Resample if necessary (simple check)
    if samplerate != SAMPLE_RATE:
        logger.error(f"Error: {filepath} is {samplerate}Hz. Please resample to {SAMPLE_RATE}Hz.")
        return ""

    # Ensure mono
    if len(audio_data.shape) > 1:
        audio_data = audio_data.mean(axis=1)

    full_transcript = []
    
    try:
        async with websockets.connect(uri) as ws:
            # Handshake (Matching production worker.py settings)
            config_msg = {
                "uid": f"benchmark_{int(time.time())}",
                "language": "en",
                "task": "transcribe",
                "model": "base.en", # This is informational for the server logs mostly
                "use_vad": True,
                "vad_parameters": {
                    "onset": 0.5,
                    "offset": 0.5
                },
                "initial_prompt": "Silence.",
                "chunk_size": 1.0,
                "condition_on_previous_text": False,
                # Production settings
                "beam_size": 5,
                "temperature": [0.0, 0.2, 0.4, 0.6, 0.8],
                "logprob_threshold": -1.0,
                "no_speech_threshold": 0.6,
                "compression_ratio_threshold": 1.35,
            }
            await ws.send(json.dumps(config_msg))
            
            # Send Audio
            # We send raw bytes (float32 le)
            # The server expects a continuous stream.
            
            async def send_audio():
                offset = 0
                while offset < len(audio_data):
                    chunk = audio_data[offset:offset+CHUNK_SIZE]
                    await ws.send(chunk.tobytes())
                    offset += CHUNK_SIZE
                    await asyncio.sleep(0.01) # Simulate real-time streaming roughly
                
                # Wait a bit for final processing then close
                await asyncio.sleep(2.0)
                await ws.close()

            async def receive_transcripts():
                try:
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        segments = []
                        if "text" in data:
                            segments.append(data)
                        elif "segments" in data:
                            segments.extend(data["segments"])
                            
                        for seg in segments:
                            if seg.get("is_final") or seg.get("completed"):
                                text = seg.get("text", "").strip()
                                if text:
                                    logger.info(f"Received: {text}")
                                    full_transcript.append(text)
                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as e:
                    logger.error(f"Receive error: {e}")

            await asyncio.gather(send_audio(), receive_transcripts())

    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return ""

    return " ".join(full_transcript)

async def main():
    parser = argparse.ArgumentParser(description="Benchmark Whisper Models")
    parser.add_argument("--input", required=True, help="Directory containing .wav and .txt files")
    parser.add_argument("--host", default="localhost", help="WhisperLive host")
    parser.add_argument("--port", default=9090, type=int, help="WhisperLive port")
    args = parser.parse_args()

    files = [f for f in os.listdir(args.input) if f.endswith(".wav")]
    if not files:
        logger.error("No .wav files found in input directory.")
        return

    total_wer = 0.0
    count = 0
    
    logger.info(f"Found {len(files)} audio files. Starting benchmark...")

    for wav_file in files:
        base_name = os.path.splitext(wav_file)[0]
        txt_file = os.path.join(args.input, f"{base_name}.txt")
        wav_path = os.path.join(args.input, wav_file)

        if not os.path.exists(txt_file):
            logger.warning(f"Skipping {wav_file}: No corresponding .txt ground truth found.")
            continue

        with open(txt_file, 'r') as f:
            reference_text = f.read().strip()

        logger.info(f"Processing {wav_file}...")
        start_time = time.time()
        hypothesis_text = await transcribe_file(wav_path, args.host, args.port)
        duration = time.time() - start_time

        # Calculate WER
        # Normalization: lower case, remove punctuation
        transforms = jiwer.Compose([
            jiwer.ToLowerCase(),
            jiwer.RemovePunctuation(),
            jiwer.RemoveMultipleSpaces(),
            jiwer.Strip(),
        ])
        
        wer = jiwer.wer(
            reference_text, 
            hypothesis_text, 
            reference_transform=transforms, 
            hypothesis_transform=transforms
        )
        
        logger.info(f"--- Result for {wav_file} ---")
        logger.info(f"Reference:  {reference_text}")
        logger.info(f"Hypothesis: {hypothesis_text}")
        logger.info(f"WER: {wer:.4f}")
        logger.info(f"Time: {duration:.2f}s")
        logger.info("-----------------------------")

        total_wer += wer
        count += 1

    if count > 0:
        avg_wer = total_wer / count
        logger.info(f"Benchmark Complete.")
        logger.info(f"Average WER: {avg_wer:.4f}")
    else:
        logger.warning("No valid test pairs processed.")

if __name__ == "__main__":
    asyncio.run(main())

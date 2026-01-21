"""Service for transcription tuning and parameter optimization."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import numpy as np
import soundfile as sf
import websockets
import jiwer
from sqlmodel import Session, select

from app.db import engine
from app.models import TuningSample, TuningRun, StreamConfig
from app.config import settings

logger = logging.getLogger(__name__)

TUNING_DATA_DIR = os.path.join(settings.data_path, "tuning")
os.makedirs(TUNING_DATA_DIR, exist_ok=True)

class TunerService:
    """Handles transcription tuning runs and parameter optimization."""

    def __init__(self):
        self.sample_rate = 16000
        self.chunk_size = 4096

    async def transcribe_with_params(
        self, 
        audio_path: str, 
        params: Dict[str, Any]
    ) -> str:
        """Transcribe an audio file with specific parameters."""
        uri = f"ws://{settings.whisper_host}:{settings.whisper_port}"
        
        try:
            audio_data, samplerate = sf.read(audio_path, dtype='float32')
        except Exception as e:
            logger.error(f"Failed to read audio file {audio_path}: {e}")
            return ""

        if samplerate != self.sample_rate:
            logger.warning(f"Audio sample rate mismatch: {samplerate} vs {self.sample_rate}")
        
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)

        full_transcript = []
        
        try:
            async with websockets.connect(uri) as ws:
                # Handshake with custom params
                config_msg = {
                    "uid": f"tuner_{int(time.time())}",
                    "language": "en",
                    "task": "transcribe",
                    "model": settings.whisper_model,
                    "use_vad": True,
                    "vad_parameters": {
                        "onset": 0.5,
                        "offset": 0.5
                    },
                    "initial_prompt": "Silence.",
                    "chunk_size": 1.0,
                    "condition_on_previous_text": False,
                    # Dynamic params from sweep
                    "beam_size": params.get("beam_size", 5),
                    "temperature": params.get("temperature", [0.0, 0.2, 0.4, 0.6, 0.8]),
                    "no_speech_threshold": params.get("no_speech_threshold", 0.6),
                    "logprob_threshold": -1.0,
                    "compression_ratio_threshold": 1.35,
                }
                await ws.send(json.dumps(config_msg))
                
                async def send_audio():
                    offset = 0
                    while offset < len(audio_data):
                        chunk = audio_data[offset:offset+self.chunk_size]
                        await ws.send(chunk.tobytes())
                        offset += self.chunk_size
                        await asyncio.sleep(0.001) # Fast stream
                    
                    await asyncio.sleep(1.0) # Wait for final
                    await ws.close()

                async def receive():
                    try:
                        while True:
                            msg = await ws.recv()
                            data = json.loads(msg)
                            if "text" in data:
                                if data.get("is_final") or data.get("completed"):
                                    full_transcript.append(data["text"].strip())
                    except websockets.exceptions.ConnectionClosed:
                        pass

                await asyncio.gather(send_audio(), receive())
        except Exception as e:
            logger.error(f"Tuning transcription failed: {e}")
            return ""

        return " ".join(full_transcript)

    async def run_sweep(self, sample_id: int):
        """Run a parameter sweep for a given sample."""
        with Session(engine) as session:
            sample = session.get(TuningSample, sample_id)
            if not sample or not sample.ground_truth:
                logger.error(f"Sample {sample_id} not found or missing ground truth")
                return

        audio_path = os.path.join(TUNING_DATA_DIR, sample.filename)
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return

        # Define the sweep grid
        beam_sizes = [1, 5]
        temperatures = [0.0, [0.0, 0.2, 0.4, 0.6, 0.8]]
        vad_thresholds = [0.4, 0.6]

        transforms = jiwer.Compose([
            jiwer.ToLowerCase(),
            jiwer.RemovePunctuation(),
            jiwer.RemoveMultipleSpaces(),
            jiwer.Strip(),
        ])

        for beam in beam_sizes:
            for temp in temperatures:
                for vad in vad_thresholds:
                    params = {
                        "beam_size": beam,
                        "temperature": temp,
                        "no_speech_threshold": vad
                    }
                    
                    start_t = time.time()
                    hyp = await self.transcribe_with_params(audio_path, params)
                    duration = time.time() - start_t
                    
                    wer = jiwer.wer(
                        sample.ground_truth,
                        hyp,
                        reference_transform=transforms,
                        hypothesis_transform=transforms
                    )
                    
                    run = TuningRun(
                        sample_id=sample_id,
                        beam_size=beam,
                        temperature=json.dumps(temp),
                        vad_threshold=vad,
                        transcription=hyp,
                        wer=wer,
                        execution_time=duration
                    )
                    
                    with Session(engine) as session:
                        session.add(run)
                        session.commit()
        
        logger.info(f"Sweep completed for sample {sample_id}")

    def apply_best_to_stream(self, sample_id: int, stream_id: int) -> Optional[Dict[str, Any]]:
        """Apply the best tuning run to a stream's Whisper settings."""
        with Session(engine) as session:
            best_run = session.exec(
                select(TuningRun)
                .where(TuningRun.sample_id == sample_id)
                .order_by(TuningRun.wer.asc())
                .limit(1)
            ).first()
            if not best_run:
                return None

            stream = session.get(StreamConfig, stream_id)
            if not stream:
                return None

            stream.whisper_beam_size = best_run.beam_size
            stream.whisper_temperature = best_run.temperature
            stream.whisper_no_speech_threshold = best_run.vad_threshold
            stream.whisper_logprob_threshold = -1.0
            stream.whisper_condition_on_previous_text = False
            stream.updated_at = datetime.utcnow()

            session.add(stream)
            session.commit()

            return {
                "beam_size": best_run.beam_size,
                "temperature": best_run.temperature,
                "no_speech_threshold": best_run.vad_threshold,
                "logprob_threshold": -1.0,
                "condition_on_previous_text": False,
                "wer": best_run.wer,
            }

tuner_service = TunerService()

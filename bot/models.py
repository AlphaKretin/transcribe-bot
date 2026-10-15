import gc
import logging
import os

from bot.config import MOONDREAM_FLAG

log = logging.getLogger(__name__)

whisper_model = None
moondream_model = None
moondream_loading = False


def load(model_size, use_moondream):
    global whisper_model
    # torch must be imported first: it puts its bundled CUDA libraries (cuBLAS, cuDNN)
    # where CTranslate2 can find them
    import torch
    from faster_whisper import WhisperModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    whisper_model = WhisperModel(model_size, device=device)
    log.info("Loaded Whisper using model size: %s (%s)", model_size, device)

    if use_moondream:
        load_moondream()
    else:
        log.info(
            "Moondream model disabled (use %s or /moondream to enable)", MOONDREAM_FLAG
        )


def load_moondream():
    global moondream_model
    import torch
    from transformers import AutoModelForCausalLM

    device = os.getenv("MOONDREAM_DEVICE") or (
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    moondream_model = AutoModelForCausalLM.from_pretrained(
        "vikhyatk/moondream2",
        revision="2025-06-21",
        trust_remote_code=True,
        device_map={"": device},
    )
    log.info("Loaded Moondream (%s)", device)


def unload_moondream():
    global moondream_model
    import torch

    moondream_model = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    log.info("Unloaded Moondream")

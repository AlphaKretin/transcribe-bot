import logging

import whisper

from bot.config import MOONDREAM_FLAG

log = logging.getLogger(__name__)

whisper_model = None
moondream_model = None


def load(model_size, use_moondream):
    global whisper_model, moondream_model

    whisper_model = whisper.load_model(model_size)
    log.info("Loaded Whisper using model size: %s", model_size)

    if use_moondream:
        from transformers import AutoModelForCausalLM

        moondream_model = AutoModelForCausalLM.from_pretrained(
            "vikhyatk/moondream2",
            revision="2025-06-21",
            trust_remote_code=True,
            # Comment/uncomment to control use of GPU for Moondream
            device_map={"": "cuda"},
        )
        log.info("Loaded Moondream")
    else:
        log.info("Moondream model disabled (use %s to enable)", MOONDREAM_FLAG)

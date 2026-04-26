"""Transcribe un archivo de audio/video usando faster-whisper en CPU.

Uso:
    python scripts/transcribe.py <input.mp4|input.wav> <output.txt> [--json out.json]

Modelo configurable por env var WHISPER_MODEL (default: "small").
Idioma fijo "es" por defecto, sobreescribible con WHISPER_LANGUAGE.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from faster_whisper import WhisperModel


def transcribe(input_path: Path, model_name: str, language: str | None) -> dict:
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(input_path),
        language=language,
        vad_filter=True,
        beam_size=1,
    )
    seg_list = []
    text_chunks = []
    for s in segments:
        seg_list.append({"start": s.start, "end": s.end, "text": s.text.strip()})
        text_chunks.append(s.text.strip())
    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "text": " ".join(text_chunks).strip(),
        "segments": seg_list,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output_txt")
    p.add_argument("--json", dest="json_out")
    args = p.parse_args()

    model_name = os.environ.get("WHISPER_MODEL", "small")
    language = os.environ.get("WHISPER_LANGUAGE") or None

    inp = Path(args.input)
    if not inp.exists():
        print(f"No existe: {inp}", file=sys.stderr)
        return 2

    result = transcribe(inp, model_name, language)
    Path(args.output_txt).write_text(result["text"] + "\n", encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

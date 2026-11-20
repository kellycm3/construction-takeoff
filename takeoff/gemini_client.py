"""Talks to Gemini: upload the PDF, extract, verify, correct."""
import json
import os
import time
from pathlib import Path
from typing import List, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from . import settings
from .prompts import CORRECT_PROMPT, EXTRACTION_PROMPT, VERIFY_PROMPT
from .schemas import PlanExtraction, Verification

T = TypeVar("T", bound=BaseModel)


def _client() -> genai.Client:
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit(
            "GEMINI_API_KEY is not set. Open the .env file in this folder and paste your key "
            "after GEMINI_API_KEY= (see README step 4)."
        )
    return genai.Client()


def _model() -> str:
    return os.environ.get("GEMINI_MODEL") or settings.DEFAULT_MODEL


def _config(schema: Type[BaseModel]) -> types.GenerateContentConfig:
    # Temperature is left at Gemini 3's default (1.0) on purpose; Google advises
    # against lowering it. HIGH media resolution helps read small dimension text.
    return types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level="high"),
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
        max_output_tokens=65536,
    )


def _call(client: genai.Client, contents: list, schema: Type[T], label: str, tries: int = 3) -> T:
    last_err = None
    for attempt in range(1, tries + 1):
        try:
            print(f"  Gemini: {label} (attempt {attempt})...")
            resp = client.models.generate_content(model=_model(), contents=contents, config=_config(schema))
            return schema.model_validate_json(resp.text)
        except ValidationError as e:
            last_err = e
            print(f"  Gemini returned data that didn't match the schema; retrying. ({e.error_count()} errors)")
        except Exception as e:  # network / rate limit / server errors
            last_err = e
            print(f"  Gemini error: {e}")
        time.sleep(5 * attempt)
    raise RuntimeError(f"Gemini failed on '{label}' after {tries} tries: {last_err}")


def _upload(client: genai.Client, pdf_path: Path):
    print(f"Uploading {pdf_path.name} ...")
    f = client.files.upload(file=str(pdf_path))
    # Wait until Google finishes processing the file
    while getattr(f.state, "name", str(f.state)) == "PROCESSING":
        time.sleep(3)
        f = client.files.get(name=f.name)
    if getattr(f.state, "name", str(f.state)) == "FAILED":
        raise RuntimeError("Gemini could not process the PDF. Is it password protected?")
    return f


def extract_from_pdf(pdf_path: Path, material_keys: List[str], out_dir: Path) -> PlanExtraction:
    """Pass A (extract) -> Pass B (verify) -> correct, up to MAX_CORRECTION_ROUNDS."""
    client = _client()
    plan = _upload(client, pdf_path)
    keys_text = "\n\nValid material_keys:\n" + "\n".join(material_keys)
    try:
        data = _call(client, [plan, EXTRACTION_PROMPT + keys_text], PlanExtraction, "reading plans (Pass A)")
        (out_dir / "1_extraction.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")

        for round_no in range(1, settings.MAX_CORRECTION_ROUNDS + 1):
            check = _call(
                client,
                [plan, VERIFY_PROMPT + "\n\nEXTRACTION JSON:\n" + data.model_dump_json()],
                Verification,
                f"checking the read (Pass B, round {round_no})",
            )
            (out_dir / f"2_verification_round{round_no}.json").write_text(
                check.model_dump_json(indent=2), encoding="utf-8"
            )
            if not check.issues:
                print("  Verification found no issues.")
                break
            print(f"  Verification found {len(check.issues)} issue(s); correcting...")
            issues_text = json.dumps([i.model_dump() for i in check.issues], indent=2)
            data = _call(
                client,
                [plan, CORRECT_PROMPT + keys_text + "\n\nISSUES:\n" + issues_text
                 + "\n\nORIGINAL EXTRACTION:\n" + data.model_dump_json()],
                PlanExtraction,
                f"correcting (round {round_no})",
            )
            (out_dir / f"3_corrected_round{round_no}.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")
            # Keep the reviewer's findings visible to you in the workbook
            data.estimator_notes.extend(f"Reviewer flagged: {i.field} - {i.problem} -> {i.fix} ({i.sheet})" for i in check.issues)
    finally:
        try:
            client.files.delete(name=plan.name)  # don't leave plans on Google's servers
        except Exception:
            pass
    return data

"""Talks to Claude: same three passes as gemini_client (extract, verify, correct)."""
import base64
import json
import os
import time
from pathlib import Path
from typing import List, Type, TypeVar

from pydantic import BaseModel, ValidationError

from . import settings
from .prompts import CORRECT_PROMPT, EXTRACTION_PROMPT, VERIFY_PROMPT
from .schemas import PlanExtraction, Verification

T = TypeVar("T", bound=BaseModel)
MAX_PDF_MB = 32


def _client():
    import anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Open the .env file in this folder and paste your Claude key "
            "after ANTHROPIC_API_KEY= (see README)."
        )
    return anthropic.Anthropic()


def _model() -> str:
    return os.environ.get("CLAUDE_MODEL") or settings.CLAUDE_DEFAULT_MODEL


def _pdf_block(pdf_path: Path) -> dict:
    size_mb = pdf_path.stat().st_size / 1_000_000
    if size_mb > MAX_PDF_MB:
        raise SystemExit(f"{pdf_path.name} is {size_mb:.0f} MB; Claude accepts up to {MAX_PDF_MB} MB per request. "
                         f"Split the plan set into smaller PDFs.")
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf",
                   "data": base64.standard_b64encode(pdf_path.read_bytes()).decode()},
        # The same PDF is sent on every pass; caching it makes passes 2 and 3 cheaper and faster.
        "cache_control": {"type": "ephemeral"},
    }


def _call(client, pdf: dict, text: str, schema: Type[T], label: str, tries: int = 3) -> T:
    import anthropic
    from anthropic.lib._parse._transform import transform_schema

    fmt = {"format": {"type": "json_schema", "schema": transform_schema(schema)}}
    use_thinking = True
    last_err = None
    for attempt in range(1, tries + 1):
        try:
            print(f"  Claude: {label} (attempt {attempt})...")
            kwargs = dict(
                model=_model(),
                max_tokens=32000,
                messages=[{"role": "user", "content": [pdf, {"type": "text", "text": text}]}],
                output_config=fmt,
            )
            if use_thinking:
                kwargs["thinking"] = {"type": "adaptive"}
            with client.messages.stream(**kwargs) as stream:
                msg = stream.get_final_message()
            body = "".join(b.text for b in msg.content if b.type == "text")
            return schema.model_validate_json(body)
        except anthropic.BadRequestError as e:
            last_err = e
            if use_thinking and "thinking" in str(e).lower():
                print("  This model doesn't accept that thinking setting; retrying without it.")
                use_thinking = False
                continue
            raise RuntimeError(f"Claude rejected the request: {e}")
        except ValidationError as e:
            last_err = e
            print(f"  Claude returned data that didn't match the schema; retrying. ({e.error_count()} errors)")
        except Exception as e:
            last_err = e
            print(f"  Claude error: {e}")
        time.sleep(5 * attempt)
    raise RuntimeError(f"Claude failed on '{label}' after {tries} tries: {last_err}")


def extract_from_pdf(pdf_path: Path, material_keys: List[str], out_dir: Path) -> PlanExtraction:
    client = _client()
    print(f"Sending {pdf_path.name} to Claude ({_model()}) ...")
    pdf = _pdf_block(pdf_path)
    keys_text = "\n\nValid material_keys:\n" + "\n".join(material_keys)

    data = _call(client, pdf, EXTRACTION_PROMPT + keys_text, PlanExtraction, "reading plans (Pass A)")
    (out_dir / "1_extraction.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")

    for round_no in range(1, settings.MAX_CORRECTION_ROUNDS + 1):
        check = _call(client, pdf, VERIFY_PROMPT + "\n\nEXTRACTION JSON:\n" + data.model_dump_json(),
                      Verification, f"checking the read (Pass B, round {round_no})")
        (out_dir / f"2_verification_round{round_no}.json").write_text(check.model_dump_json(indent=2), encoding="utf-8")
        if not check.issues:
            print("  Verification found no issues.")
            break
        print(f"  Verification found {len(check.issues)} issue(s); correcting...")
        issues_text = json.dumps([i.model_dump() for i in check.issues], indent=2)
        data = _call(client, pdf, CORRECT_PROMPT + keys_text + "\n\nISSUES:\n" + issues_text
                     + "\n\nORIGINAL EXTRACTION:\n" + data.model_dump_json(),
                     PlanExtraction, f"correcting (round {round_no})")
        (out_dir / f"3_corrected_round{round_no}.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")
        data.estimator_notes.extend(f"Reviewer flagged: {i.field} - {i.problem} -> {i.fix} ({i.sheet})" for i in check.issues)
    return data

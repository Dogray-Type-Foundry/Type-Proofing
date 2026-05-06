"""Subprocess entry point for PDF generation.

The worker speaks JSON Lines on stdout so Swift can stream progress,
diagnostics, and completion without blocking the UI process.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from typing import Any


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _load_config(path: str | None) -> dict[str, Any]:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return json.load(sys.stdin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Type Proofing PDF worker")
    parser.add_argument("--config", help="Path to JSON generation config")
    parser.add_argument(
        "--mode",
        choices=["final", "preview-fragment"],
        default="final",
        help="Generation mode. Defaults to final for backwards compatibility.",
    )
    args = parser.parse_args(argv)

    # Ensure imports resolve when launched directly from the copied python-lib.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        from engine import generate_preview_fragment, generate_proof

        config = _load_config(args.config)
        _emit({"type": "started"})
        if args.mode == "preview-fragment":
            result = generate_preview_fragment(config, event_callback=_emit)
        else:
            result = generate_proof(config, event_callback=_emit)
        if result.get("path"):
            _emit({"type": "completed", "result": result})
            return 0
        _emit({"type": "failed", "result": result, "message": "Proof generation failed"})
        return 1
    except KeyboardInterrupt:
        _emit({"type": "cancelled"})
        return 130
    except Exception as exc:
        _emit(
            {
                "type": "failed",
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

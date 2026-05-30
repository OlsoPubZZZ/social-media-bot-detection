"""Detection configuration — weights and thresholds.

These live in one place so the community can tune detection and contribute
presets without touching detector logic. Load a custom config from JSON with
:func:`Config.from_json` and pass it through the analysis pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict


@dataclass
class Config:
    # --- detector weights (relative contribution to the aggregate score) ---
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "duplicate_text": 1.0,
            "timing_burst": 0.8,
            "coordination": 1.2,
            "account_weakness": 0.7,
            "ratio_anomaly": 0.6,
            "llm_text_judgment": 1.0,
        }
    )

    # --- duplicate text ---
    # Min number of accounts sharing (near-)identical text to form a cluster.
    duplicate_min_cluster: int = 3
    # Simhash hamming distance (out of 64) below which two texts are "near-dup".
    near_dup_max_hamming: int = 6
    # Ignore very short texts for dup detection (emoji-only, "nice", etc.).
    duplicate_min_chars: int = 4

    # --- timing burst ---
    # A window is a burst if it holds >= this multiple of the expected rate.
    burst_rate_multiplier: float = 4.0
    burst_window_seconds: int = 60
    burst_min_events: int = 5

    # --- account weakness ---
    new_account_days: int = 30
    extreme_follow_ratio: float = 20.0  # following / max(followers, 1)
    handle_digit_ratio: float = 0.4  # share of digits in handle that looks generated

    # --- coordination ---
    coordination_min_group: int = 3

    # --- scoring thresholds (aggregate suspicion in [0, 1]) ---
    genuine_below: float = 0.25
    suspicious_at: float = 0.5
    # Below this much "evidence coverage" an item is LOW_CONFIDENCE regardless.
    min_confidence_coverage: float = 0.34

    # --- LLM enrichment (optional; only used when an LLM client is supplied) ---
    # Default model. Overridable; Haiku is far cheaper for this classification
    # path, but per Anthropic guidance we don't downgrade the default for you.
    llm_model: str = "claude-opus-4-8"
    # Max number of ambiguous comments routed to the LLM per run (cost control).
    llm_max_items: int = 25
    # Output token ceiling for the batched judge call.
    llm_max_tokens: int = 2048

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        base = cls()
        for key, value in data.items():
            if key == "weights" and isinstance(value, dict):
                base.weights.update(value)
            elif hasattr(base, key):
                setattr(base, key, value)
        return base


DEFAULT_CONFIG = Config()

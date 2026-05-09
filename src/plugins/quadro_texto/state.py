"""
state.py — Anti-repetition shuffle-bag for Quadro Texto plugin.

Persists last N style signatures to disk so random mode never repeats
the same combination consecutively.

State file: {plugin_dir}/state.json
Format:
{
  "history": ["sig1", "sig2", ...],   // last MAX_HISTORY signatures
  "bag_remaining": ["sig3", "sig4"]   // shuffle bag of remaining combos
}
"""

import json
import logging
import os
import random

logger = logging.getLogger(__name__)

MAX_HISTORY = 4   # how many past signatures to remember


def _state_path(plugin_dir: str) -> str:
    return os.path.join(plugin_dir, "state.json")


def _load(plugin_dir: str) -> dict:
    path = _state_path(plugin_dir)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"quadro_texto: could not read state.json: {e}")
    return {"history": [], "bag_remaining": []}


def _save(plugin_dir: str, state: dict):
    path = _state_path(plugin_dir)
    try:
        with open(path, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning(f"quadro_texto: could not write state.json: {e}")


def pick_combination(plugin_dir: str, all_combinations: list[str]) -> str:
    """Return a style signature, guaranteed to differ from recent history.

    Uses a shuffle-bag strategy:
    - Maintains a "bag" of remaining unplayed combos.
    - When bag is empty, refill (minus last MAX_HISTORY entries).
    - Always picks from bag, never from history.
    """
    if len(all_combinations) == 1:
        return all_combinations[0]

    state = _load(plugin_dir)
    history: list = state.get("history", [])
    bag: list     = state.get("bag_remaining", [])

    # Validate bag (may contain stale keys after code update)
    valid_set = set(all_combinations)
    bag = [s for s in bag if s in valid_set]

    # Remove recent history from available pool
    forbidden = set(history[-MAX_HISTORY:])
    available = [s for s in (bag or all_combinations) if s not in forbidden]
    if not available:
        # All exhausted — reset and allow anything except the very last
        last = history[-1] if history else None
        available = [s for s in all_combinations if s != last]
        if not available:
            available = list(all_combinations)

    chosen = random.choice(available)

    # Update bag (remove chosen, refill if empty)
    if chosen in bag:
        bag.remove(chosen)
    if not bag:
        bag = [s for s in all_combinations if s not in forbidden and s != chosen]
        random.shuffle(bag)

    history.append(chosen)
    history = history[-MAX_HISTORY:]

    _save(plugin_dir, {"history": history, "bag_remaining": bag})
    return chosen


def record_fixed(plugin_dir: str, signature: str):
    """Record a fixed (non-random) signature so history stays accurate."""
    state = _load(plugin_dir)
    history: list = state.get("history", [])
    history.append(signature)
    history = history[-MAX_HISTORY:]
    _save(plugin_dir, {**state, "history": history})


# ── Illustration-style anti-repeat (simple last-N history) ────────────────────

_ILLUS_HISTORY_KEY = "illus_history"
_ILLUS_CONCRETE = ["clean", "doodle", "sketch", "cartoon", "sticker"]

def pick_illustration_style(plugin_dir: str) -> str:
    """Pick a concrete illustration style, avoiding recent repeats.

    Used when illustration_style == 'random'.
    """
    state = _load(plugin_dir)
    history: list = [
        s for s in state.get(_ILLUS_HISTORY_KEY, []) if s in _ILLUS_CONCRETE
    ]
    forbidden = set(history[-2:])  # avoid the most recent styles
    available = [s for s in _ILLUS_CONCRETE if s not in forbidden]
    if not available:
        available = _ILLUS_CONCRETE

    chosen = random.choice(available)
    history.append(chosen)
    history = history[-4:]
    _save(plugin_dir, {**state, _ILLUS_HISTORY_KEY: history})
    return chosen

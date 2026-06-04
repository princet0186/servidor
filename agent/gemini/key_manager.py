"""Circular Gemini API key rotation with rate-limit retry."""
import os
import logging
import time
from typing import List, Optional

logger = logging.getLogger("servidor.key_manager")


class GeminiKeyManager:
    def __init__(self):
        self.keys: List[str] = []
        self.current_index: int = 0
        self._failed_keys: dict[str, float] = {}  # key -> timestamp of last failure
        self._cooldown_seconds: int = 60
        self._load_keys()

    def _load_keys(self):
        keys = []
        # Load numbered keys: GEMINI_API_KEY_1 through GEMINI_API_KEY_10
        for i in range(1, 11):
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key and key.strip():
                keys.append(key.strip())

        # Also check the base key
        base_key = os.getenv("GOOGLE_API_KEY", "")
        if base_key and base_key.strip():
            keys.append(base_key.strip())

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for k in keys:
            if k not in seen:
                seen.add(k)
                unique.append(k)

        self.keys = unique
        if self.keys:
            logger.info(f"Loaded {len(self.keys)} Gemini API key(s)")
        else:
            logger.warning("No Gemini API keys found in environment")

    def get_next_key(self) -> Optional[str]:
        """Get the next available key, skipping recently failed ones."""
        if not self.keys:
            self._load_keys()

        if not self.keys:
            return None

        now = time.time()
        attempts = 0

        while attempts < len(self.keys):
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)

            # Check if key is in cooldown
            fail_time = self._failed_keys.get(key)
            if fail_time and (now - fail_time) < self._cooldown_seconds:
                attempts += 1
                continue

            # Clear expired cooldown
            if fail_time:
                del self._failed_keys[key]

            return key

        # All keys in cooldown — return least recently failed
        if self._failed_keys:
            oldest_key = min(self._failed_keys, key=self._failed_keys.get)
            del self._failed_keys[oldest_key]
            return oldest_key

        return self.keys[0] if self.keys else None

    def mark_failed(self, key: str):
        """Mark a key as rate-limited."""
        self._failed_keys[key] = time.time()
        logger.warning(f"API key ...{key[-6:]} marked as rate-limited, cooling down {self._cooldown_seconds}s")

    def is_configured(self) -> bool:
        """Check if at least one key is available."""
        if not self.keys:
            self._load_keys()
        return len(self.keys) > 0

    @property
    def key_count(self) -> int:
        return len(self.keys)

    @property
    def active_keys(self) -> int:
        now = time.time()
        cooled = sum(1 for k, t in self._failed_keys.items() if (now - t) < self._cooldown_seconds)
        return len(self.keys) - cooled


# Singleton
key_manager = GeminiKeyManager()

"""
Backward-compatible configuration module.
This module is deprecated — use config.settings instead.

All imports are redirected to the new config module for consistency.
Legacy code using 'from config import settings' will continue to work.
"""

# ────────────────────────────────────────────────────────────────────────────
# DEPRECATION WARNING: This file is maintained for backward compatibility only.
# New code should use: from config import settings
# ────────────────────────────────────────────────────────────────────────────

from config.settings import settings, Settings

__all__ = ["settings", "Settings"]

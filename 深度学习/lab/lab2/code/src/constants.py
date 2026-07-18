"""Shared constants for name classification."""

from __future__ import annotations

import string

ALLOWED_CHARACTERS = string.ascii_letters + " .,;'-_"
NUM_CHARACTERS = len(ALLOWED_CHARACTERS)

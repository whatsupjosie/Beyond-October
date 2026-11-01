"""Application object compatibility wrapper.

Authoritative route ownership lives in iteration_wallet.server. This module
exists only so older callers importing iteration_wallet.app can resolve the same
FastAPI app without creating a second server implementation.
"""

from iteration_wallet.server import app

__all__ = ["app"]

"""Standalone Iteration Wallet package.

Current normalized core: BlackBox, Vault, Ceremony, Gatekeeper, Oubliette,
Identity, Cradle, and Archive. Compatibility wrappers are intentionally thin and
must not become duplicate subsystem implementations.
"""

__version__ = "2.1-standalone-normalized"

__all__ = [
    "app",
    "blackbox",
    "ceremony",
    "cli",
    "gatekeeper",
    "guard",
    "identity",
    "notification_manager",
    "server",
    "vault",
    "vault_v21",
]

"""Errors raised by the PubPartner identity-vessel runtime."""

from __future__ import annotations


class VesselError(RuntimeError):
    """Base class for vessel failures."""


class VesselFormatError(VesselError):
    """The file is not a supported PubPartner vessel."""


class VesselIntegrityError(VesselError):
    """The vessel failed an integrity or audit-chain check."""


class VesselReadOnlyError(VesselError):
    """A write was attempted through a read-only mount."""


class VesselConflictError(VesselError):
    """A requested write conflicts with authoritative vessel state."""


class VesselPermissionError(VesselError):
    """The requested record is outside the caller's visibility scope."""


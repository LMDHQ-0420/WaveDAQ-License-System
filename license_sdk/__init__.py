"""Reusable offline license verification SDK for desktop products."""

from .verifier import LicenseError, allows, require_valid_license, verify_license

__all__ = ["LicenseError", "allows", "require_valid_license", "verify_license"]

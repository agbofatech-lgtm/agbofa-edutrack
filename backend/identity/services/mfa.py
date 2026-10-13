"""Testable, provider-free TOTP enrollment and verification for identity MFA."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import struct
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from identity.models import MfaCredential, User

TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
TOTP_WINDOW_STEPS = 1
ENCRYPTION_VERSION = b"\x01"


def privileged_account_requires_mfa(user: User) -> bool:
    """Apply MFA to Django platform administrators without inventing school roles."""

    return bool(user.is_active and (user.is_staff or user.is_superuser))


def _encryption_key() -> bytes:
    value = getattr(settings, "MFA_ENCRYPTION_KEY", "")
    if not isinstance(value, str) or not value:
        raise ImproperlyConfigured("MFA_ENCRYPTION_KEY is not configured.")
    try:
        key = base64.b64decode(
            value.encode("ascii") + b"=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (UnicodeEncodeError, binascii.Error) as error:
        raise ImproperlyConfigured(
            "MFA_ENCRYPTION_KEY must be URL-safe base64 for 32 random bytes."
        ) from error
    if len(key) != 32:
        raise ImproperlyConfigured(
            "MFA_ENCRYPTION_KEY must decode to exactly 32 bytes."
        )
    return key


def _associated_data(user: User) -> bytes:
    return f"agbofa-edutrack:mfa:v1:{user.pk}".encode()


def encrypt_totp_secret(user: User, secret: str) -> bytes:
    """Encrypt a base32 TOTP seed with AES-256-GCM and a per-value nonce."""

    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_encryption_key()).encrypt(
        nonce,
        secret.encode("ascii"),
        _associated_data(user),
    )
    return ENCRYPTION_VERSION + nonce + ciphertext


def decrypt_totp_secret(user: User, encrypted: bytes) -> str:
    """Decrypt only a seed bound to the expected account and version."""

    payload = bytes(encrypted)
    if len(payload) < 1 + 12 + 16 or payload[:1] != ENCRYPTION_VERSION:
        raise ImproperlyConfigured("Stored MFA credential has an unsupported format.")
    try:
        plaintext = AESGCM(_encryption_key()).decrypt(
            payload[1:13],
            payload[13:],
            _associated_data(user),
        )
        return plaintext.decode("ascii")
    except (InvalidTag, UnicodeDecodeError) as error:
        raise ImproperlyConfigured(
            "MFA_ENCRYPTION_KEY cannot decrypt the stored credential."
        ) from error


def generate_totp_secret() -> str:
    """Generate a 160-bit RFC 6238 secret encoded for common authenticator apps."""

    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    normalized = secret.strip().upper()
    padded = normalized + "=" * (-len(normalized) % 8)
    return base64.b32decode(padded, casefold=True)


def _hotp(secret: bytes, counter: int) -> str:
    digest = hmac.new(secret, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(binary % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def generate_totp_code(secret: str, at: datetime | float | None = None) -> str:
    """Return an RFC 6238 SHA-1 six-digit code; exposed for deterministic tests."""

    if at is None:
        timestamp = timezone.now().timestamp()
    elif isinstance(at, datetime):
        timestamp = at.timestamp()
    else:
        timestamp = at
    counter = int(timestamp // TOTP_PERIOD_SECONDS)
    return _hotp(_decode_secret(secret), counter)


def _matching_counter(secret: str, code: str, now: datetime) -> int | None:
    if len(code) != TOTP_DIGITS or not code.isascii() or not code.isdigit():
        return None
    current_counter = int(now.timestamp() // TOTP_PERIOD_SECONDS)
    try:
        decoded_secret = _decode_secret(secret)
    except (binascii.Error, ValueError):
        return None
    for counter in range(
        max(0, current_counter - TOTP_WINDOW_STEPS),
        current_counter + TOTP_WINDOW_STEPS + 1,
    ):
        if hmac.compare_digest(_hotp(decoded_secret, counter), code):
            return counter
    return None


def _enrollment_ttl() -> int:
    ttl = getattr(settings, "IDENTITY_MFA_SETUP_TTL_SECONDS", 300)
    if not isinstance(ttl, int) or ttl <= 0:
        raise ImproperlyConfigured("MFA setup expiry must be a positive integer.")
    return ttl


def begin_mfa_enrollment(user: User) -> str:
    """Create or resume a short-lived pending TOTP enrollment for a platform admin."""

    if not privileged_account_requires_mfa(user):
        raise PermissionError("MFA enrollment is restricted to privileged accounts.")
    now = timezone.now()
    with transaction.atomic():
        try:
            credential = MfaCredential.objects.select_for_update().get(user=user)
        except MfaCredential.DoesNotExist:
            credential = None

        if credential is not None and credential.is_enabled:
            raise PermissionError("The account already has an enabled MFA factor.")
        if (
            credential is not None
            and credential.setup_expires_at is not None
            and credential.setup_expires_at > now
        ):
            return decrypt_totp_secret(user, credential.secret_ciphertext)

        secret = generate_totp_secret()
        values = {
            "secret_ciphertext": encrypt_totp_secret(user, secret),
            "is_enabled": False,
            "setup_expires_at": now + timedelta(seconds=_enrollment_ttl()),
            "enabled_at": None,
            "last_verified_counter": None,
        }
        if credential is None:
            MfaCredential.objects.create(user=user, **values)
        else:
            for field, value in values.items():
                setattr(credential, field, value)
            credential.save(update_fields=[*values, "updated_at"])
    return secret


def get_pending_mfa_secret(user: User) -> str | None:
    """Return a pending seed only while its server-side enrollment window is open."""

    try:
        credential = MfaCredential.objects.get(user=user, is_enabled=False)
    except MfaCredential.DoesNotExist:
        return None
    if (
        credential.setup_expires_at is None
        or credential.setup_expires_at <= timezone.now()
    ):
        return None
    return decrypt_totp_secret(user, credential.secret_ciphertext)


def mfa_is_enabled(user: User) -> bool:
    return MfaCredential.objects.filter(user=user, is_enabled=True).exists()


def provisioning_uri(secret: str) -> str:
    """Build a standards-based URI for manual enrollment in an authenticator app."""

    label = quote("AGBOFA EduTrack", safe="")
    query = urlencode(
        {
            "secret": secret,
            "issuer": "AGBOFA EduTrack",
            "algorithm": "SHA1",
            "digits": str(TOTP_DIGITS),
            "period": str(TOTP_PERIOD_SECONDS),
        }
    )
    return f"otpauth://totp/{label}?{query}"


def verify_mfa_code(user: User, code: str, *, setup: bool = False) -> bool:
    """Verify and consume a TOTP counter once, locking the credential row."""

    now = timezone.now()
    with transaction.atomic():
        try:
            credential = MfaCredential.objects.select_for_update().get(user=user)
        except MfaCredential.DoesNotExist:
            return False

        if setup:
            if credential.is_enabled:
                return False
            if (
                credential.setup_expires_at is None
                or credential.setup_expires_at <= now
            ):
                return False
        elif not credential.is_enabled:
            return False

        secret = decrypt_totp_secret(user, credential.secret_ciphertext)
        counter = _matching_counter(secret, code, now)
        if counter is None:
            return False
        if (
            credential.last_verified_counter is not None
            and counter <= credential.last_verified_counter
        ):
            return False

        credential.last_verified_counter = counter
        update_fields = ["last_verified_counter", "updated_at"]
        if setup:
            credential.is_enabled = True
            credential.enabled_at = now
            credential.setup_expires_at = None
            update_fields.extend(["is_enabled", "enabled_at", "setup_expires_at"])
        credential.save(update_fields=update_fields)
    return True


def account_requires_mfa(user: User) -> bool:
    """Require MFA for platform admins and keep an enrolled factor enforced after demotion."""

    return privileged_account_requires_mfa(user) or mfa_is_enabled(user)

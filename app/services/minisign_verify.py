"""Pure-Python minisign / Ed25519 signature verifier (Phase 32, UPD-02, T-32-01).

The one genuinely new security primitive of Phase 32: authenticate a downloaded
``manifest.txt`` against the vendored public key (``app/minisign.pub``) BEFORE any
version is trusted or any archive is unpacked. The actual elliptic-curve math is
delegated ENTIRELY to ``cryptography`` (never hand-rolled — CLAUDE.md safety); this
module only parses the tiny, documented minisign envelope.

Envelope layout (minisign spec, docs/RELEASE.md:40-60):
- public key file: line 1 = untrusted comment, LAST non-empty line =
  ``base64(alg[2] || key_id[8] || pubkey[32])``.
- ``.minisig`` file: line 1 = untrusted comment, line 2 =
  ``base64(alg[2] || key_id[8] || signature[64])``.

Algorithm-agnostic (32-RESEARCH Pitfall 1): ``Ed`` verifies over the raw message,
``ED`` over ``blake2b(message, digest_size=64)`` (minisign's prehashed mode). A
key-id mismatch or any ``cryptography`` error is a silent ``False`` — never raises.
"""

import base64
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def _parse_pubkey(text: str) -> tuple[bytes, bytes]:
    """Return ``(key_id, pubkey)`` from a minisign public-key file.

    The first line is an untrusted comment; the LAST non-empty line carries the
    base64 payload ``alg || key_id[8] || pubkey[32]``. The first 2 bytes are the
    ``Ed`` signature-algorithm marker.
    """
    key_line = [ln for ln in text.splitlines() if ln.strip()][-1]
    raw = base64.b64decode(key_line)
    assert raw[:2] == b"Ed"  # signature algorithm marker
    return raw[2:10], raw[10:42]


def verify_minisign(manifest_bytes: bytes, sig_text: str, pubkey_text: str) -> bool:
    """True iff ``sig_text`` is a valid minisign signature over ``manifest_bytes``.

    Rejects (returns False, never raises) a signature whose key-id does not match
    the vendored public key, and any ``cryptography`` InvalidSignature / parse
    error. Algorithm-agnostic across minisign's ``Ed`` (raw) and ``ED`` (prehashed
    BLAKE2b-512) modes.
    """
    try:
        key_id, pk = _parse_pubkey(pubkey_text)
        # Line 1 of a .minisig is the untrusted comment; line 2 is the payload.
        lines = [ln for ln in sig_text.splitlines() if ln.strip()]
        sig_raw = base64.b64decode(lines[1])
        alg, sig_key_id, signature = sig_raw[:2], sig_raw[2:10], sig_raw[10:74]
        if sig_key_id != key_id:  # wrong key ⇒ reject, never authenticate
            return False
        # 'ED' = prehashed BLAKE2b-512, 'Ed' = raw message (32-RESEARCH Pitfall 1).
        message = (
            hashlib.blake2b(manifest_bytes, digest_size=64).digest()
            if alg == b"ED"
            else manifest_bytes
        )
        Ed25519PublicKey.from_public_bytes(pk).verify(signature, message)
        return True
    except Exception:  # cryptography.exceptions.InvalidSignature, parse errors, …
        return False


def sha256_matches(archive_path, expected_hex: str) -> bool:
    """True iff the SHA-256 of the archive bytes equals ``expected_hex``.

    Mirrors ``build_release.verify_manifest`` (T-31-03): re-hash the archive and
    compare hex; a single flipped byte flips the result to False.
    """
    actual = hashlib.sha256(Path(archive_path).read_bytes()).hexdigest()
    return actual == expected_hex

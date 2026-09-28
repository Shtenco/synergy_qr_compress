from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256


def _sha256_hex(data: bytes) -> str:
    return sha256(data).hexdigest()


def _require_sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be lowercase SHA-256 hex")


@dataclass(frozen=True)
class FederationOfflinePayloadManifest:
    payload_id: str
    payload_type: str
    issuer_repo: str
    target_repo: str
    canonical_content_sha256: str
    encoding_profile: str
    created_at: str
    expires_at: str
    replay_nonce: str
    signature_algorithm: str
    signing_key_reference: str
    shared_model_sha256: str | None = None
    temporal_slot: int | None = None
    frame_set_sha256: str | None = None
    authorization_conferred: bool = False
    schema: str = "synergy.offline-payload-manifest/v1"
    transport_authority: str = "NONE"

    @classmethod
    def bind_payload(
        cls,
        *,
        payload_id: str,
        payload_type: str,
        issuer_repo: str,
        target_repo: str,
        canonical_bytes: bytes,
        encoding_profile: str,
        created_at: str,
        expires_at: str,
        replay_nonce: str,
        signature_algorithm: str,
        signing_key_reference: str,
        shared_model_sha256: str | None = None,
        temporal_slot: int | None = None,
        frame_set_bytes: bytes | None = None,
    ) -> "FederationOfflinePayloadManifest":
        return cls(
            payload_id=payload_id,
            payload_type=payload_type,
            issuer_repo=issuer_repo,
            target_repo=target_repo,
            canonical_content_sha256=_sha256_hex(canonical_bytes),
            encoding_profile=encoding_profile,
            created_at=created_at,
            expires_at=expires_at,
            replay_nonce=replay_nonce,
            signature_algorithm=signature_algorithm,
            signing_key_reference=signing_key_reference,
            shared_model_sha256=shared_model_sha256,
            temporal_slot=temporal_slot,
            frame_set_sha256=_sha256_hex(frame_set_bytes) if frame_set_bytes is not None else None,
            authorization_conferred=False,
        )

    def __post_init__(self) -> None:
        _require_sha256(self.canonical_content_sha256, "canonical_content_sha256")
        if self.authorization_conferred:
            raise ValueError("QR/QTC transport cannot confer authorization")
        if len(self.replay_nonce) < 16:
            raise ValueError("replay_nonce must have at least 16 characters")
        if self.shared_model_sha256 is not None:
            _require_sha256(self.shared_model_sha256, "shared_model_sha256")
        if self.frame_set_sha256 is not None:
            _require_sha256(self.frame_set_sha256, "frame_set_sha256")
        if self.encoding_profile in {"QTC2_EXACT", "QTC2_PATCH"}:
            if self.shared_model_sha256 is None or self.temporal_slot is None:
                raise ValueError("QTC2 exact/patch requires shared model hash and temporal slot")
        created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= created:
            raise ValueError("expires_at must be later than created_at")
        if any(token in self.signing_key_reference.upper() for token in ("PRIVATE_KEY=", "SEED=", "MNEMONIC=")):
            raise ValueError("raw signing secrets are forbidden; use a key reference")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

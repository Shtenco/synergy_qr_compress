import unittest
from datetime import datetime, timedelta, timezone

from federation.offline_manifest import FederationOfflinePayloadManifest


class FederationOfflineManifestTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)

    def test_qtc2_patch_binds_shared_model(self):
        manifest = FederationOfflinePayloadManifest.bind_payload(
            payload_id="payment-ref-0001",
            payload_type="PAYMENT_INTENT_REFERENCE",
            issuer_repo="Shtenco/synergy_pay_system",
            target_repo="Shtenco/synergy_pay_system",
            canonical_bytes=b"payment-intent-reference",
            encoding_profile="QTC2_PATCH",
            shared_model_sha256="a" * 64,
            temporal_slot=1234,
            created_at=self.now.isoformat(),
            expires_at=(self.now + timedelta(minutes=10)).isoformat(),
            replay_nonce="nonce-1234567890abcdef",
            signature_algorithm="ML-DSA-65",
            signing_key_reference="kms://synergy/metapay/offline-v1",
            frame_set_bytes=b"frame-set",
        )
        self.assertFalse(manifest.authorization_conferred)
        self.assertEqual(manifest.transport_authority, "NONE")
        self.assertEqual(manifest.shared_model_sha256, "a" * 64)
        self.assertIsNotNone(manifest.frame_set_sha256)

    def test_qtc2_patch_without_model_rejected(self):
        with self.assertRaisesRegex(ValueError, "shared model"):
            FederationOfflinePayloadManifest.bind_payload(
                payload_id="budget-proof-0001",
                payload_type="PUBLIC_BUDGET_PROOF_REFERENCE",
                issuer_repo="Shtenco/blochain_budget",
                target_repo="Shtenco/blochain_budget",
                canonical_bytes=b"proof-ref",
                encoding_profile="QTC2_PATCH",
                created_at=self.now.isoformat(),
                expires_at=(self.now + timedelta(hours=1)).isoformat(),
                replay_nonce="nonce-fedcba0987654321",
                signature_algorithm="ML-DSA-65",
                signing_key_reference="kms://synergy/budget/offline-v1",
            )

    def test_raw_private_key_reference_rejected(self):
        with self.assertRaisesRegex(ValueError, "raw signing secrets"):
            FederationOfflinePayloadManifest.bind_payload(
                payload_id="node-ref-0001",
                payload_type="NODE_ENROLLMENT_REFERENCE",
                issuer_repo="Shtenco/synergy_meta_os",
                target_repo="Shtenco/synergy_meta_os",
                canonical_bytes=b"node-enrollment-ref",
                encoding_profile="QTC2_STANDALONE",
                created_at=self.now.isoformat(),
                expires_at=(self.now + timedelta(minutes=5)).isoformat(),
                replay_nonce="nonce-0011223344556677",
                signature_algorithm="ML-DSA-65",
                signing_key_reference="PRIVATE_KEY=deadbeef",
            )


if __name__ == "__main__":
    unittest.main()

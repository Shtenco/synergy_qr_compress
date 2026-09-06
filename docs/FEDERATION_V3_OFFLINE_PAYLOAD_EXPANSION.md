# Federation V3 — QR / Offline Compact Payload expansion

This repository supports compact offline transfer of typed federation artifacts, especially where connectivity is intermittent.

## Target payloads
- payment intents/receipts that are safe to represent offline;
- identity/public-key references;
- evidence hashes/manifests;
- device/node enrollment bundles;
- scientific sample/protocol references;
- public-budget proof references.

## Requirements
- versioned schema;
- payload type and issuer;
- content hash;
- expiry/freshness;
- replay protection where relevant;
- signature/verification metadata;
- deterministic decode;
- strict size/error-correction benchmarks.

## Boundaries
QR transport does not confer trust or authorization by itself. Payment settlement still belongs to `synergy_pay_system`; accounting interpretation to `synergy_financial_os`; trust verification to the relevant cryptographic/trust layer.

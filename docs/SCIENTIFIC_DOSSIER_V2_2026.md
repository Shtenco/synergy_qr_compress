# QTD3 — temporal shared-model compression research

## Original research contribution

The QR Compress project explores **content reconstruction relative to an external shared historical model**, where the transmitted representation may encode references to already available bytes instead of retransmitting them. It is especially suited to versioned repositories, time-ordered corpora and repeated object families. A high model-coverage percentage must not be confused with an equally high standalone compression ratio when the shared model has nonzero acquisition/storage cost.

The source [qtd3.py](../qr_temporal/qtd3.py) implements reproducible historical models and COPY/LITERAL tokenization, model serialization with content digests, varint encoding, candidate compression engines, a blind/walk-forward packaging path and byte-exact validation. It contains strategy labels for external LZ, FastCDC, line-reference, lineage and standalone fallback.

## Formal metrics

Let the original target have n bytes and let c bytes be reconstructed by exact COPY references into the shared model. The reported coverage is

$$
\mathrm{Coverage}=100\frac{c}{n}\%.
$$

For a target archive of payload size z, metadata/header h and externally required model of size m, the **full-system storage cost** is not just z+h: it also includes the relevant share of m. For K targets sharing one model, a simple amortized aggregate cost per target is

$$
\overline{B}=\frac{m+\sum_{i=1}^{K}(z_i+h_i)}{K}.
$$

This metric makes shared-model benchmarks comparable to standalone compressors only when the evaluation workload and model creation are disclosed.

## Algorithmic details

QTD3 model entries contain path, nanosecond time, SHA-256 digest and bytes. The decoder validates model identity, each reconstructed entry and target length; output exceeding the declared size is rejected. Lossless correctness requires

$$
\operatorname{Decode}(\operatorname{Encode}(x,M),M)=x
$$

for each legal input x and exactly the expected model M.

## Scientific experiment

Separate training blobs from all future targets by time, prohibit identical target hashes in the model when benchmarking blind generalization, and vary model size, repository history, degree of code churn and unseen-file similarity. Compare standalone zstd/brotli/lzma, QTC1, QTC2 and QTD3 on **the same files** with wall-clock encode/decode, peak memory, wire bytes, model amortization and corruption testing.

## Research and product value

The design offers a path toward temporal source archives, repository synchronization and bandwidth-constrained data exchange. Its key scientific idea is **temporal side-information coding with explicit exactness and honest model accounting**.

[QTD3 implementation](../qr_temporal/qtd3.py) · [Historical tests](../tests/test_qtd3.py) · [Blind proof](../proofs/QTD3_WALK_FORWARD_REAL_PROOF.md)

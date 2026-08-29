# V5-X2 architecture

1. Legacy V4 exact candidate is always included.
2. Segment-MDL uses one outer integrity hash and compact per-segment route metadata.
3. Exact format-normalization candidates are admitted only when byte-for-byte reconstruction is proven.
4. Optional stage-2 recompression is accepted only when its complete final representation is smaller.
5. No third compression stage in the production search.

# SHTENCO QR Compress — Temporal QR Codec (QTC1)

Новый независимый проект на базе идей `Shtenco/ai_compress`: **lossless exact round-trip, MDL/UMD-style routing, проверяемые benchmark и строгая валидация**, но специально для упаковки данных в QR-последовательности с UNIX temporal anchor.

## Что реализовано

- **QTC1 lossless container** с SHA-256 исходных данных.
- **Adaptive codec selector**: `raw`, `zlib-9`, `bz2-9`, `lzma-extreme`.
- Два lossless preprocessing surface: `identity` и `delta8`; выбирается минимальный operational-MDL score.
- **TemporalAnchor64**: timestamp в UNIX nanoseconds.
- **Temporal content tag**: 20 бит хэша payload кодируются непосредственно в младшие биты timestamp; время изменяется максимум примерно на 0.524 ms до ближайшей congruent-метки (грубая верхняя граница <1.049 ms).
- **Multi-QR framing**: большие архивы автоматически делятся на нумерованные QR-кадры с `timestamp + frame index + total + CRC32`.
- Декодер отвергает повреждение по temporal tag, CRC32 и SHA-256.
- Exact tests для текста, случайных байтов, перестановки кадров и corruption rejection.
- CI Python 3.10–3.13.

## Важное про «99,9999% в UNIX timestamp»

Одна UNIX-метка — конечное число бит. Она **не может lossless хранить произвольный файл любого размера** без внешнего словаря/модели: это нарушило бы информационный предел.

Поэтому QTC1 делает физически корректную реализацию идеи:

`SOURCE → reversible transforms → adaptive compression → residual payload`

`                                      ↘ UNIX-ns temporal anchor + embedded content tag`

`container → QR frame 1 … QR frame N → exact recovery`

Timestamp является **временным адресом и компактным проверочным carrier**, а остальная энтропия хранится в residual. Для специализированного временного корпуса следующий слой проекта может обучать общий temporal dictionary/model; тогда доля residual действительно может приближаться к нулю на распределении, но это должно измеряться benchmark, а не объявляться заранее.

## Формат QTC1

Header содержит magic/version, codec id, transform id, adjusted UNIX timestamp in ns, original byte length, compressed payload length и SHA-256.

Младшие 20 бит timestamp содержат BLAKE2s-derived tag compressed payload. Проверка не заменяет SHA-256 — это быстрый temporal consistency gate.

## Быстрый старт

```bash
python -m pip install -e ".[dev]"
pytest -q
qr-compress encode input.bin -o input.qtc --qr-dir qr_frames
qr-compress inspect input.qtc
qr-compress decode input.qtc -o restored.bin
python benchmark.py input.bin
```

## API

```python
from qr_temporal import pack, unpack, split_frames, join_frames
src = b"information" * 1000
p = pack(src)
frames = split_frames(p.blob, p.unix_ns)
_, restored_container = join_frames([f.bytes for f in frames])
assert unpack(restored_container) == src
```

## Roadmap

1. Temporal corpus model / shared dictionaries.
2. zstd + Brotli + rANS optional engines.
3. Fountain-code QR mode for frame loss.
4. Reed-Solomon at inter-frame layer.
5. Video/animated QR transport.
6. Merkle chunk index and random access.
7. Learned MDL router trained on corpus classes.
8. Benchmark against raw QR, ZIP/QR, zstd/QR and ai_compress engines.
9. Explicit `temporal_coverage` metric targeting 99.9999% only where a corpus model empirically achieves it.

## Provenance

Architecture borrows the **methodological principles** from `Shtenco/ai_compress` (multiple lossless engines, MDL-style selection, exact round-trip and SHA verification). The original repository is not modified.

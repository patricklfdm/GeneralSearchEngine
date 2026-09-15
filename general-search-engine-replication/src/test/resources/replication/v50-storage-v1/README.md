# Independent replicated-storage (1,0) golden directory

`node-2/` contains the exact seven production-format files. `SHA256SUMS` pins each
whole-file hash; the inventory lives outside the replica directory intentionally.
Python generated these bytes without using Java storage code. Java tests copy them
to a fresh temporary directory, open them, then compare Java-generated files byte for
byte. The Python test regenerates and verifies this inventory independently.

The fixture has three immutable voters, genesis epoch 1, one promise at epoch 2,
three entries (NO_OP, ADD_ALL, UPDATE), and a proof through index 2 from voters 1 and
2. Entry 3 is uncommitted. Opaque payloads are fixture strings, not V4 document codec
encodings; neither reader loads an application codec. No application state is applied.

Regenerate into a new directory, then explicitly compare against the frozen files:

```bash
python3 -m scripts.v50.storage_format generate /tmp/absent-v50-storage-fixture
python3 -m scripts.v50.storage_format inspect /tmp/absent-v50-storage-fixture
```

The format specification is `docs/v5x/v5.0/PHASE_2_STORAGE_FORMAT.md` at repository
root. This fixture is distinct from Phase 1's logical JSON examples and wire frames.

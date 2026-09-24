"""Execution partition only; the frozen workload/cell parameters remain authoritative."""
MODES = ('published-v4.4-local', 'published-v5.0-configured', 'candidate-v5.1-automatic')
CELLS = tuple(('healthy', mode) for mode in MODES) + (('read-heavy', MODES[2]), ('sustained', MODES[2]))
SHARDS = {
    'published-controls': CELLS[:2],
    'automatic-healthy': CELLS[2:3],
    'automatic-concurrent': CELLS[3:],
}

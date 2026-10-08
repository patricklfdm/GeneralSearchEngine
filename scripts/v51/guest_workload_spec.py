"""Closed offline rich tapes. Selecting a tape never admits a cloud preset."""
from . import cloud_package as package, performance_model as m, performance_plan as plan, remote_schedule as schedule

CELLS = package.WORKLOAD_CELLS
CASES = package.CANONICAL_WORKLOADS


def selection(config):
    return package.workload_selection(config)


def specs(config):
    return schedule.windows(*selection(config))


def final_state(config):
    state = m.initial(plan.load())
    for spec in specs(config):
        for call in spec['calls']:
            if call['operation'] in m.OP_IDS:
                state.apply(m.OP_IDS[call['operation']], bytes.fromhex(call['payload']))
    return state


def scope(mode, cell):
    m.need((mode, cell) in CASES, 'offline canonical owned workload scope')
    return 'owned-canonical-' + mode + '-' + cell


SCOPES = {scope(mode, cell): (mode, cell) for mode, cell in CASES}

"""Closed offline rich tapes. Selecting a tape never admits a cloud preset."""
from . import cloud_package as package, performance_model as m, performance_plan as plan, remote_schedule as schedule

CELLS = ('healthy', 'read-heavy', 'sustained')
CASES = tuple((mode, 'healthy') for mode in package.MODES) + tuple(
    (package.MODES[2], cell) for cell in CELLS[1:])


def selection(config):
    value = config.get('workload')
    if 'workload' not in config:
        return 'healthy', 'experiment'
    m.need(config['execution'] == 'local-guest-service-only' and 'faultCell' not in config and
           type(value) is dict and set(value) == {'cell', 'preset'} and value['preset'] == 'canonical' and
           (config['mode'], value['cell']) in CASES, 'offline canonical guest workload scope')
    return value['cell'], value['preset']


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

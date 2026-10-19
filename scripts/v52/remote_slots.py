"""Stable semantic command slots for one selected history/node/session."""
from . import remote_command as command
from .evidence import need


def slot(owner,kind,payload):
    command.validate_binding(owner)
    need(type(kind) is str and kind in command.COMMANDS and type(payload) is dict,'remote planned command')
    if kind in ('start-voter','stop-voter'):
        need(set(payload)=={'generation'} and type(payload['generation']) is int and payload['generation'] in (1,2),'remote planned generation')
        need(payload['generation']==1 or owner['history']=='leader-sigkill-retained-restart','remote undeclared reopen generation')
        return kind+':'+str(payload['generation'])
    if kind=='declared-fault':
        need(set(payload)=={'action'} and type(payload['action']) is str,'remote planned fault fields')
        allowed={'leader-sigkill-retained-restart':('sigkill',),'follower-snapshot-carried-token':('partition','heal')}
        need(payload['action'] in allowed.get(owner['history'],()),'remote undeclared fault action')
        return kind+':'+payload['action']
    need(not payload,'remote planned command payload')
    return kind


def request(owner,kind,payload=None):
    payload={} if payload is None else payload
    name=slot(owner,kind,payload)
    key=dict(bindingSha256=command.digest(command.encoded(owner)),slot=name)
    identity=command.digest(command.encoded(key))[:32]
    return command.request(owner,identity,kind,payload)


def validate(value,owner):
    command.validate_request(value,owner)
    expected=request(owner,value['command'],value['payload'])
    need(value==expected,'remote changed semantic command identity')
    return value


def execute(store,value,handler):
    validate(value,store.owner)
    return store.execute(value,handler)

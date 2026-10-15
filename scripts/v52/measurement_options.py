"""Closed consumer settings for M01 defaults and later M02/M03 schedules."""
from .evidence import need

SCHEMA='gse-v52-read-measurement-parameters-v1'
FILE='measurement-options.json'


def parameters(family='M01',*,wait=5000,pending=64):
    value=dict(schema=SCHEMA,family=family,pendingLimit=pending,waitTimeoutMillis=wait,
               operationTimeoutMillis=120000 if family=='M03' else 9600)
    return validate(value)


def validate(value):
    need(type(value) is dict and set(value)=={'schema','family','pendingLimit','waitTimeoutMillis','operationTimeoutMillis'} and
         value['schema']==SCHEMA and all(type(value[k]) is int for k in ('pendingLimit','waitTimeoutMillis','operationTimeoutMillis')),
         'measurement read parameter shape')
    family=value['family'];pending=value['pendingLimit'];wait=value['waitTimeoutMillis'];operation=value['operationTimeoutMillis']
    need((family=='M01' and (pending,wait,operation)==(64,5000,9600)) or
         (family=='M02' and pending==64 and wait in (0,1000,5000) and operation==9600) or
         (family=='M03' and pending in (4,65) and wait==60000 and operation==120000),'measurement undeclared read parameters')
    return dict(value)

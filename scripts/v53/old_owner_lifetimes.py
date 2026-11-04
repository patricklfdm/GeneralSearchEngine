"""Explicit ordered cold-owner scopes, without filtering original observations.

The historical single (event index, scope) pair stays valid. Multiple opens must
declare ordered, distinct pairs; a scope label alone is never an opening force.
"""
from .membership_model import need


def entries(value):
    if type(value) is tuple and len(value)==2 and type(value[0]) is int:return (value,)
    return value


def validate(value,*,reason,owners=None,maximum=None):
    result={} if value is None else value
    need(type(result) is dict,reason)
    for node,raw in result.items():
        pairs=entries(raw)
        need(type(node) is str and bool(node) and (owners is None or node in owners) and
             type(pairs) is tuple and pairs and all(type(v) is tuple and len(v)==2 and
                 type(v[0]) is int and v[0]>=0 and (maximum is None or v[0]<maximum) and
                 type(v[1]) is str and bool(v[1]) for v in pairs),reason)
        need(all(a[0]<b[0] for a,b in zip(pairs,pairs[1:])) and len({v[1] for v in pairs})==len(pairs),reason)
    return result


def scope(lifetimes,node,at,default=None):
    if node not in lifetimes:return default
    active=default
    for start,name in entries(lifetimes[node]):
        if at<start:break
        active=name
    return active

"""Bounded formal-history exports using the existing measurement bundle limits.

The control response carries an inventory digest, not the potentially large
inventory body. The first immutable archive member supplies that exact body.
"""
from . import measurement_bundle as bundle,remote_voter_scope as scope,remote_command as c
from .evidence import need,encoded,digest

SCHEMA='gse-v52-voter-formal-export-v1'


def formal(config):return scope.formal(config.get('binding',{}))


def summary(index):
    expanded=bundle.validate_index(index);raw=encoded(index)+b'\n'
    need(len(raw)<=bundle.LIMITS['inventory'] and expanded+len(raw)<=bundle.LIMITS['expanded'],
         'formal export inventory/expansion bound')
    return dict(files=len(index),bytes=len(raw),sha256=digest(raw),expandedBytes=expanded)


def descriptor(value):
    need(type(value) is dict and set(value)=={'files','bytes','sha256','expandedBytes'} and
         type(value['files']) is int and 0<value['files']<bundle.LIMITS['files'] and
         type(value['bytes']) is int and 0<value['bytes']<=bundle.LIMITS['inventory'] and
         type(value['expandedBytes']) is int and 0<=value['expandedBytes'] and
         value['expandedBytes']+value['bytes']<=bundle.LIMITS['expanded'],'formal export inventory descriptor')
    c.hex_value(value['sha256'],64,'formal export inventory hash');return value


def manifest(value,config,sha):
    need(formal(config),'formal export requires exact history')
    need(type(value) is dict and set(value)=={'schema','configSha256','node','bytes','sha256','inventory','terminal'} and
         value['schema']==SCHEMA and value['configSha256']==sha and value['node']==config['node'],
         'formal export identity')
    need(type(value['bytes']) is int and 0<value['bytes']<=bundle.LIMITS['compressed'],'formal export archive bound')
    c.hex_value(value['sha256'],64,'formal export archive hash');descriptor(value['inventory']);return value


def verify_inventory(index,meta):
    descriptor(meta['inventory']);need(summary(index)==meta['inventory'],'formal export inventory changed')
    node=meta['node'];need(node in ('node-1','node-2','node-3'),'formal export node')
    need(all(name.split('/')[0]==node or name.split('/')[0].startswith(node+'-') for name in index),
         'formal export foreign collection path')
    metadata={scope.control_name(node,g)+'/'+name for g in (1,2) for name in ('lifecycle.json','ssh-streams.json')}
    need(not metadata & set(index),'formal export circular collection metadata')
    return index


def aggregate(metas):
    """Admit total receiver expansion before downloading the next whole export."""
    files=expanded=0
    for meta in metas:
        need(meta['schema']==SCHEMA,'formal export mixed collection formats');s=descriptor(meta['inventory'])
        files+=s['files'];expanded+=s['expandedBytes']+s['bytes']
    need(files<bundle.LIMITS['files'] and expanded<=bundle.LIMITS['expanded'],'formal export combined bound')
    return dict(files=files,expandedBytes=expanded)

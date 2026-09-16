"""Derived execution policy; the accepted workload JSON and offered rates stay frozen."""
from .cloud_common import require
from .cloud_workload_plan import read_plan


def schedule(profile, *, control=False):
    p=read_plan()
    if profile=='local-qualification':
        local=p['localQualification']
        return dict(local, windows=['warmup',*p['workload']['windows'],'sustained'])
    require(profile in p['profiles'],'unknown remote profile')
    windows=['warmup',*p['workload']['windows']]
    if profile=='failure-drill' and not control:windows=['warmup']
    if profile=='canonical':windows.append('sustained')
    return dict(warmupCycles=20,cyclesPerWindow=120 if profile=='canonical' else 30,
        sustainedCalls=6000 if profile=='canonical' else 0,healthyIntervalNanos=100_000_000,
        sustainedIntervalNanos=50_000_000,pacing='fixed-rate',windows=windows,
        maximumRunSeconds=sum(p['profiles'][profile]['reservationsSeconds']),
        cells=[v['name'] for v in p['profiles'][profile]['cells']])


def measurement_seconds(profile,name):
    s=schedule(profile)
    if name=='sustained':return s['sustainedCalls']*s['sustainedIntervalNanos']/1e9
    cycles=s['warmupCycles'] if name=='warmup' else s['cyclesPerWindow']
    return cycles*10*s['healthyIntervalNanos']/1e9

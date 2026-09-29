"""Once-only healthy backup and stopped-voter public V4.4 restore qualification."""
import shutil
from . import cloud_package as package, guest_bootstrap as bootstrap, guest_authority as authority
from . import performance_model as m, remote_command as c, remote_schedule as schedule


def exported(cell):
    value=authority.inventory(cell/'export')
    m.need(set(value)==set(bootstrap.SOURCE), 'guest backup closed inventory')
    return value


def create(service):
    m.need(service.config['mode'] in package.MODES[1:] and service.jvm is not None and not service.jvm.closed,
           'guest backup requires live replicated voter')
    # A new command ID cannot repeat the backup, including after a lost result.
    for spec in schedule.windows('healthy','experiment'):
        value=c.read(service.root/('window-healthy-'+spec['window'])/'result.json')
        m.need(value['status']=='PASS' and len(value['calls'])==len(spec['calls']), 'guest backup requires complete healthy tape')
    c.write_once(service.root/'backup-claim.json',dict(config=service.config))
    m.need(not (service.cell/'export').exists() and not (service.cell/'export').is_symlink(), 'guest backup destination consumed')
    response=service.jvm.command('backup')
    m.need(response['outcome']=='SUCCESS','guest backup failed')
    result=dict(response=response,files=exported(service.cell))
    c.write_once(service.root/'backup-result.json',result)
    return result


def restore(service):
    m.need(service.config['mode'] in package.MODES[1:] and service.jvm is not None and service.jvm.closed,
           'guest restore requires stopped replicated voter')
    backup=c.read(service.root/'backup-result.json')
    m.need(c.read(service.root/'backup-claim.json')==dict(config=service.config) and
           exported(service.cell)==backup['files'], 'guest restore backup changed')
    c.write_once(service.root/'restore-claim.json',dict(config=service.config,backupSha256=m.sha(m.canonical(backup))))
    root=service.root/'restored-check';root.mkdir(mode=0o700)
    process=service.oneshot('restore',service.java(package.MODES[0],root,'restore',service.plan,service.cell/'export'))
    m.need(exported(service.cell)==backup['files'], 'guest restore changed backup')
    result=dict(process=process,files=backup['files'])
    c.write_once(service.root/'restore-result.json',result)
    return result


def capture(service, output):
    # Preserve partial original evidence on a failed backup/restore as well.
    # Only independent validation can require complete, successful results.
    output.mkdir(mode=0o700)
    for name in ('backup-claim.json','backup-result.json','restore-claim.json','restore-result.json','restore.stdout','restore.stderr'):
        source=service.root/name
        m.need(not source.is_symlink(), 'guest backup evidence bound/type')
        if not source.exists():continue
        m.need(source.is_file() and not source.is_symlink() and source.stat().st_size<=1<<20, 'guest backup evidence bound/type')
        shutil.copyfile(source,output/name)
    source=service.cell/'export'
    m.need(not source.is_symlink(), 'guest backup export type')
    if source.exists():
        before=authority.inventory(source,allow_empty=True)
        shutil.copytree(source,output/'export')
        m.need(authority.inventory(output/'export',allow_empty=True)==before==authority.inventory(source,allow_empty=True),
               'guest backup changed during collection')

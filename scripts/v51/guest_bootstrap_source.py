"""Qualification-only producer in an independent filesystem view.

Source parts are shared local immutable files, not an implementation of cloud
source transport. Receiver installation/sealing still enters its verified package.
"""
from pathlib import Path
import sys
import time
from . import performance_model as m, remote_command as c, cloud_guest as guest


class ViewSource:
    offline = True
    scope = 'qualification-shared-source-paths'
    def __init__(self, views, package, *, clock=time.monotonic, sleep=time.sleep):
        self.views,self.package,self.clock,self.sleep=views,Path(package),clock,sleep
        self.started=False; self.submits=0; self.queries=0

    def prepare(self, configs, deadline):
        m.need(not self.started and self.clock()<deadline,'bootstrap source consumed/deadline')
        self.started=True; config=configs[0]; target=guest.validate(config)
        relative=target.relative_to(self.views.cell)
        retained=self.views.root/'producer'/relative
        m.need(not retained.parent.parent.exists(),'bootstrap source view consumed')
        value=c.request(config['binding'],m.sha(m.canonical(config))[:32],'prepare-cell',dict(distribute=True))
        self.submits+=1
        try:
            raw=self.views.execute('producer',[sys.executable,'-I',str(self.package/'guest.py'),'bootstrap','prepare','--deadline',str(deadline)],
                m.canonical(config),deadline)
            answer=m.strict_json(raw)
        except (ConnectionError,TimeoutError): answer=None
        while True:
            m.need(self.clock()<deadline,'bootstrap source unresolved; no replay')
            if answer is not None:
                m.need(all(answer.get(k)==v for k,v in dict(schema='gse-v51-command-receipt-v1',bindingSha256=value['bindingSha256'],
                    commandId=value['commandId'],requestSha256=m.sha(m.canonical(value))).items()),'bootstrap source receipt identity')
                m.need(answer.get('state') in ('NOT_FOUND','UNCERTAIN','RUNNING','SUCCEEDED','FAILED','CANCELLED'), 'bootstrap source receipt state')
                if answer['state'] in ('SUCCEEDED','FAILED','CANCELLED'):
                    m.need(answer['state']=='SUCCEEDED','bootstrap source preparation failed')
                    exports=answer['result']['bootstrap']
                    return [dict(row,folder=str(retained/'bootstrap'/row['node'])) for row in exports]
            self.sleep(min(.05,max(0,deadline-self.clock())))
            m.need(self.clock()<deadline and self.queries<4096,'bootstrap source query budget'); self.queries+=1
            if (retained/'store').is_dir(): answer=c.CommandStore(retained/'store',config['binding']).query(value)

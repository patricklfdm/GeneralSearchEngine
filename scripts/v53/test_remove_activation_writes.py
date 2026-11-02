"""REMOVE adapter exercises the shared writer predicates, not mocked helpers."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import remove_network_evidence as n
from .test_joining_grant_write_chain import fixture as capture


def fixture():
    raw=b'selected';digest=n.sha(raw);nodes=('node-1','node-2');events=[];rows=[];files={};records={}
    selected=dict(ballot=dict(proposer='node-1'),view='view',cut=dict(index=5),sources=[])
    for node in nodes:
        basis=(node+'-basis').encode();basis_id='b-'+node
        selected['sources'].append(dict(voter=node,basisId=basis_id,basisDigest=n.sha(basis)))
        records[basis]=dict(basisId=basis_id)
        files[1,node]={'members':{'selected.gsr':raw,'basis.gsr':basis,'promise.gsr':b'promise','original.image':b'image'},
                       'sources/'+basis_id+'/source.gscp':b'packet'}
    records[raw]=selected
    def add(point,node='node-1',**values):
        at=len(events);events.append(dict(node=node,event=point,**values));return at
    def grant(node):
        for v in capture():add(v['event'],node)
    def select(node):
        for point in ('SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN'):add(point,node)
    def install(node):
        names=['INSTALL_RESERVED','INSTALL_DIRECTORY_CREATED','INSTALL_MANIFEST_WRITTEN','INSTALL_MANIFEST_FORCED',
            'INSTALL_MEMBER_WRITTEN','INSTALL_MEMBER_FORCED','INSTALL_IMAGE_WRITTEN','INSTALL_IMAGE_FORCED',
            'INSTALL_MEMBER_WRITTEN','INSTALL_MEMBER_FORCED','INSTALL_MEMBER_WRITTEN','INSTALL_MEMBER_FORCED',
            'INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_WRITTEN','INSTALL_SELECTOR_FORCED','INSTALL_SELECTOR_RENAMED',
            'INSTALL_PARENT_FORCED','CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED',
            'CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED','INSTALL_BEFORE_RETURN']
        for point in names:add(point,node)
    def row(kind,sent,received,offered,delivered):
        q=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),view='view',ballot=selected['ballot'],
            sequence=1 if kind=='PREPARE' else 2,payload=dict(promise=n.sha(b'promise')) if kind=='PREPARE' else dict(selection=digest))
        a=dict(payload=dict(basis=n.sha(b'node-2-basis')) if kind=='PREPARE' else dict(selection=digest,cut=selected['cut']))
        return dict(kind=kind,answer='PROMISE' if kind=='PREPARE' else 'INSTALL_ACK',request=q,response=a,
                    sent=sent,received=received,offered=offered,delivered=delivered)
    grant('node-1');sent=add('SEND');received=add('REQUEST');grant('node-2')
    offered=add('REPLY');delivered=add('DELIVERY');rows.append(row('PREPARE',sent,received,offered,delivered))
    select('node-1');sent=add('SEND');received=add('REQUEST');select('node-2');install('node-2')
    offered=add('REPLY');delivered=add('DELIVERY');rows.append(row('SELECTED',sent,received,offered,delivered))
    install('node-1');add('ROUND_INSTALLED',record=digest)
    return events,rows,SimpleNamespace(phases=[dict(SELECTED=raw)],installed=files),records


class RemoveActivationWritesTest(unittest.TestCase):
    def check(self,data):
        events,rows,history,records=data
        with patch.object(n.f,'decode',side_effect=lambda raw,*args:records[raw]), \
             patch.object(n.c,'current',side_effect=lambda files:('',files['members'],{})), \
             patch.object(n.c.p,'decode',return_value=dict(images={'image':5})):
            return n.activations(events,rows,history)

    def test_complete_capture_and_both_installer_sequences(self):
        self.assertEqual(dict(originalGrants=2,boundInstallReplies=1,proposerInstallations=1),self.check(fixture()))

    def test_both_grants_require_original_write_boundaries(self):
        for node in ('node-1','node-2'):
            data=fixture();next(v for v in data[0] if v['node']==node and v['event']=='BASIS_PREFIX_WRITTEN')['event']='OMITTED'
            with self.subTest(node=node),self.assertRaisesRegex(ValueError,'^REMOVE network durable grant order$'):self.check(data)

    def test_both_installs_require_original_write_boundaries(self):
        for node,reason in [('node-1','joining network proposer complete installation order'),('node-2','REMOVE network durable installation order')]:
            data=fixture();next(v for v in data[0] if v['node']==node and v['event']=='INSTALL_MANIFEST_WRITTEN')['event']='OMITTED'
            with self.subTest(node=node),self.assertRaisesRegex(ValueError,'^'+reason+'$'):self.check(data)

    def test_unbound_capture_callback_is_not_silently_ignored(self):
        data=fixture();data[0].append(dict(node='node-1',event='BASIS_WRITTEN'))
        with self.assertRaisesRegex(ValueError,'^REMOVE network unbound grant capture callback$'):self.check(data)


if __name__=='__main__':unittest.main()

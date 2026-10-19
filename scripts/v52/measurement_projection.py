"""Compact application projection from independently chosen entries.

Callers must establish quorum/force/selection first. This validates the closed
measurement workload and each complete publication without retaining snapshots.
Application sequence counts chosen updates, never attempts or NO_OPs.
"""
from scripts.v51 import runtime_evidence as physical
from . import measurement_model as model,measurement_oracle as oracle
from .evidence import need,encoded,digest

MAX_ENTRIES=8192


class Projection:
    def __init__(self,manifest,genesis,chosen,offered):
        need(type(chosen) is dict and len(chosen)<=MAX_ENTRIES,'measurement chosen entry bound')
        need(type(offered) is list and len(offered)<=180,'measurement offered update bound')
        self.manifest=manifest;self.chosen=chosen
        indexes,documents=physical.application(physical.raw(genesis['application']))
        need(genesis['baseSequence']==1 and [dict(id=k,value=v) for k,v in documents.items()]==model.corpus(),'measurement projection genesis')
        self.indexes=sorted(indexes,key=lambda r:r['field'])
        program=[r['document'] for r in model.program() if r['kind']=='update'];program_ordinals={encoded(doc):i for i,doc in enumerate(program)}
        offered_by_document={encoded(c['document']):c for c in offered}
        need(len(offered_by_document)==len(offered) and all(doc in program_ordinals for doc in offered_by_document),'measurement undeclared/duplicate offered update')
        need(len({c['opId'] for c in offered})==len(offered),'measurement duplicate update identity')
        supplied=[program_ordinals[encoded(c['document'])] for c in offered]
        need(all(a<b for a,b in zip(supplied,supplied[1:])),'measurement offered update order')
        ordered=sorted(chosen.items(),key=lambda item:item[1]['index'])
        self.anchors=[];self.sequence_at=[1];self.ordinals=[];self.update_entries={};self.states={1:dict(sequence=1,documents=model.corpus())};self.publications=0
        last=-1;state=dict(documents);sequence=1
        for index,(entry_digest,entry) in enumerate(ordered,1):
            need(entry['index']==index,'measurement chosen prefix gap/conflict');self.anchors.append(entry_digest)
            command=physical.application_command(entry['operation'],physical.raw(entry['payload']))
            need(command['operation'] in (2,9),'measurement undeclared chosen operation')
            if command['operation']==2:
                document=command['documents'][0];identity=encoded(document)
                need(identity in offered_by_document,'measurement chosen update lacks offered call')
                ordinal=program_ordinals[identity];need(ordinal>last,'measurement duplicate/reordered chosen update');last=ordinal
                call=offered_by_document[identity];self.update_entries[call['opId']]=dict(index=index,sequence=sequence+1,ordinal=ordinal,digest=entry_digest)
                self.ordinals.append(ordinal);state[document['id']]=document['value'];sequence+=1
                self.states[sequence]=dict(sequence=sequence,documents=[dict(id=k,value=v) for k,v in state.items()])
            self.sequence_at.append(sequence)
        self.state_hashes={seq:digest(encoded(value)) for seq,value in self.states.items()}
        for call in offered:
            if call['outcome']=='SUCCESS':need(call['opId'] in self.update_entries,'measurement successful update not chosen')
            elif call['outcome']=='NOT_SUBMITTED':need(call['opId'] not in self.update_entries,'measurement rejected update was chosen')
            else:need(call['outcome'] in ('INDETERMINATE','PENDING'),'measurement undeclared update outcome')

    def publication(self,snapshot):
        anchors=snapshot['anchors'];index=len(anchors)
        need(index<=len(self.anchors) and all(anchor['entryDigest']==self.anchors[i] for i,anchor in enumerate(anchors)),
             'measurement publication differs from chosen ancestry')
        sequence=self.sequence_at[index]
        indexes,documents=physical.application(physical.raw(snapshot['application']))
        state=dict(sequence=sequence,documents=[dict(id=k,value=v) for k,v in documents.items()])
        need(snapshot['applicationSequence']==sequence and indexes==self.indexes and digest(encoded(state))==self.state_hashes[sequence],
             'measurement publication application state')
        last=self.anchors[index-1] if index else None
        proof=physical.frame(snapshot['terminalProof'],'PROOF',self.manifest) if index else None
        need((proof is not None and proof['index']==index and proof['entryDigest']==last) if index else snapshot['terminalProof'] is None,
             'measurement publication terminal proof')
        self.publications+=1
        return dict(index=index,sequence=sequence,last=last,epoch=proof['epoch'] if proof else 0,
                    stateSha256=self.state_hashes[sequence])

    def update_response(self,call,latest_index):
        chosen=self.update_entries.get(call['opId'])
        if call['outcome']=='SUCCESS':need(chosen is not None and chosen['index']<=latest_index,'measurement update response before chosen publication')
        elif call['outcome']=='NOT_SUBMITTED':need(chosen is None,'measurement rejected update was chosen')
        # INDETERMINATE/PENDING conveys no rollback; its chosen effect remains in
        # every subsequent state and in the real published-core replay.
        return chosen

    def query_input(self,cuts):return oracle.prepare_selected(cuts,self.ordinals)

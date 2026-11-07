"""Queue frame positions bound to checked originals, without decoded payload caches."""
import base64
from collections.abc import Mapping
import re
from . import segmented_evidence as segmented
from . import source_queue_evidence as queue

need=queue.need


class Frames(Mapping):
    def __init__(self,source,side):
        need(type(source) is segmented.Reader and type(side) is str and side in ('request','response'),
             'segmented queue original frames')
        self.source=source;self.side=side;self.positions={}

    def record(self,index,digest,kind,size):
        """Called only after the queue reader checks the complete exchange."""
        need(type(index) is int and 0<=index<len(self.source) and
             type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest) and
             type(kind) is str and kind in queue.f.catalog()['wire'] and
             type(size) is int and 48<=size<=segmented.ROW_BYTES,
             'segmented queue frame position')
        previous=self.positions.setdefault(digest,(index,kind,size))
        need(previous[1:]==(kind,size),'segmented queue duplicate frame binding')

    def __iter__(self):return iter(self.positions)
    def __len__(self):return len(self.positions)

    def __getitem__(self,digest):
        index,kind,size=self.positions[digest]
        raw=base64.b64decode(self.source[index][self.side],validate=True)
        need(len(raw)==size and queue.sha(raw)==digest,'segmented queue original frame binding')
        decoded=queue.frame(raw)
        need(decoded[0]==kind,'segmented queue original frame binding')
        return decoded

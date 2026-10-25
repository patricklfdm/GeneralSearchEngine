"""Read the fixed OfflineApplication fixture's real 1.2 backup image independently."""
import struct
import uuid
from scripts.v43 import derived_format_v12 as core
from . import pending_context_evidence as e
from .retirement_source_process_evidence import same


def _table():
    rows=[]
    for value in range(256):
        for _ in range(8):value=(value>>1)^0x82F63B78 if value&1 else value>>1
        rows.append(value)
    return tuple(rows)


_CRC32C=_table()


def crc32c(raw):
    value=0xffffffff
    for byte in raw:value=_CRC32C[(value^byte)&255]^(value>>8)
    return value^0xffffffff


def uncheck(raw,minimum,member):
    e.need(len(raw)>=minimum,member+' is truncated')
    e.need(crc32c(raw[:-4])==int.from_bytes(raw[-4:],'big'),member+' CRC32C mismatch')
    return core.Cursor(raw[:-4])


def image_members(raw):
    e.need(24<len(raw)<=64*e.MIB and struct.unpack('>4sHHI',raw[:12])==(b'GSAI',1,3,len(raw)-12),'bootstrap validation image header')
    offset=12;result={}
    for name in ('gse-backup-checkpoint','gse-backup-manifest','gse-backup-metadata'):
        e.need(offset+4<=len(raw),'bootstrap validation image member size');size=int.from_bytes(raw[offset:offset+4],'big');offset+=4
        e.need(0<size<=len(raw)-offset,'bootstrap validation image member size');result[name]=raw[offset:offset+size];offset+=size
    e.need(offset==len(raw),'bootstrap validation image trailer')
    # application() checks each member's CRC immediately before parsing it.
    e.need(result['gse-backup-manifest'][-16:-4]==b'\0'*12,'bootstrap validation canonical manifest administration')
    return result


def application(raw,history,sequence,documents):
    """Decode this fixed fixture's real core backup; never trust producer JSON."""
    members=image_members(raw);identity=uuid.UUID(history).int;halves=(identity>>64,identity&((1<<64)-1));profile=core.profile_digest()
    def header(cursor,magic):
        same(cursor.unpack('>QhhQQ'),(magic,1,2,*halves),'cross-view application identity')
    def indexes(cursor,count):
        e.need(count==1 and cursor.unpack('>B')[0]==1 and cursor.string(1024)=='value' and cursor.string(128,True)=='','cross-view application indexes')
    meta=uncheck(members['gse-backup-metadata'],64,'cross-view metadata');header(meta,core.METADATA_MAGIC)
    e.need(meta.string(128)=='gse-durable','cross-view application family');size=meta.unpack('>I')[0]
    e.need(size==len(core.profile_bytes()) and meta.take(size)==core.profile_bytes() and meta.take(32)==profile,'cross-view application profile')
    names=['fixture-store','fixture-schema','fixture-codec'];same([meta.string(128) for _ in names],names,'cross-view application codec')
    bounds=meta.unpack('>iiiiiqqqi');same(bounds[:-1],(1,1024,65536,1000,10000,1024,1<<30,1<<20),'cross-view application limits');indexes(meta,bounds[-1]);meta.finish()
    checkpoint=uncheck(members['gse-backup-checkpoint'],88,'cross-view checkpoint');header(checkpoint,core.CHECKPOINT_MAGIC)
    e.need(checkpoint.take(32)==profile,'cross-view application profile');seq,next_doc,live,count=checkpoint.unpack('>qiii')
    e.need((seq,next_doc,live)==(sequence,len(documents),len(documents)),'cross-view application sequence/documents');indexes(checkpoint,count)
    e.need(checkpoint.unpack('>i')[0]==len(documents),'cross-view application slots')
    for key,value in documents:
        e.need(checkpoint.unpack('>Bi')==(1,4) and checkpoint.unpack('>i')[0]==key,'cross-view application key')
        payload=(str(key)+':'+value).encode('utf-8');length=checkpoint.unpack('>i')[0]
        e.need(length==len(payload) and checkpoint.take(length)==payload,'cross-view application document bytes')
    checkpoint.finish()
    manifest=uncheck(members['gse-backup-manifest'],160,'cross-view manifest')
    same(manifest.unpack('>Qhh'),(core.BACKUP_MAGIC,1,2),'cross-view backup version')
    e.need(manifest.string(128)=='gse-backup' and manifest.string(128)=='gse-durable' and manifest.unpack('>hh')==(1,2) and manifest.take(32)==profile,'cross-view backup profile')
    same(manifest.unpack('>QQq'),(*halves,sequence),'cross-view backup history/sequence');same([manifest.string(128) for _ in names],names,'cross-view backup codec')
    e.need(manifest.unpack('>iI')==(1,2),'cross-view backup members');payloads={k:v for k,v in members.items() if k!='gse-backup-manifest'}
    for name,data in sorted(payloads.items()):
        e.need(manifest.string(128)==name and manifest.unpack('>Q')[0]==len(data) and manifest.take(32).hex()==e.digest(data),'cross-view backup member binding')
    e.need(manifest.take(32).hex()==e.digest(core._backup_preimage(payloads,profile,halves,sequence,*names,1)),'cross-view backup content identity')
    e.need(manifest.unpack('>q')[0]==0 and manifest.string(256,True)=='','cross-view backup administration');manifest.finish()


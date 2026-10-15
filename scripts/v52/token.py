"""Independent client-token byte specification, with no production decoder imports."""
import hashlib
import struct
import uuid

DOMAIN = b'gse-replica-read-token/1\0'


def decode(raw):
    if len(raw) != 112 or raw[:4] != b'GSRT': raise ValueError('INVALID_TOKEN')
    if raw[4] != 1: raise ValueError('UNSUPPORTED_TOKEN_VERSION')
    if raw[5:8] != b'\0'*3 or hashlib.sha256(DOMAIN+raw[:80]).digest() != raw[80:]:
        raise ValueError('INVALID_TOKEN')
    index = int.from_bytes(raw[72:80], 'big', signed=True)
    if index < 0: raise ValueError('INVALID_TOKEN')
    return dict(version=1, groupId=str(uuid.UUID(bytes=raw[8:24])), historyId=str(uuid.UUID(bytes=raw[24:40])),
                manifestDigest=raw[40:72].hex(), index=index)


def encode(value):
    if type(value['version']) is not int or value['version'] != 1: raise ValueError('UNSUPPORTED_TOKEN_VERSION')
    if type(value['index']) is not int or not 0 <= value['index'] <= (1<<63)-1: raise ValueError('INVALID_TOKEN')
    digest=bytes.fromhex(value['manifestDigest'])
    if len(digest)!=32 or digest.hex()!=value['manifestDigest']:raise ValueError('INVALID_TOKEN')
    body=(b'GSRT\x01\0\0\0'+uuid.UUID(value['groupId']).bytes+uuid.UUID(value['historyId']).bytes+
          digest+struct.pack('>q',value['index']))
    return body+hashlib.sha256(DOMAIN+body).digest()

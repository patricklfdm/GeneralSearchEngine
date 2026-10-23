"""Original selected BASIS inventory, independently decoded; no force/ownership inference."""
import struct
import json
from pathlib import Path
from . import format_fixture as f
from .context_evidence import majority, authority
from .applied_end_evidence import digest
from .membership_model import need

FILE = 'selected-sources.gsr'
MAXIMUM = 6 * 16384


def cuts(raw, selected):
    need(type(raw) is bytes and 0 < len(raw) <= MAXIMUM, 'selected originals capacity')
    refs = selected['sources']; voters = [r['voter'] for r in refs]
    need(2 <= len(refs) <= 6 and voters == sorted(set(voters)), 'selected originals voters')
    majority(selected['cut']['view'], voters)
    need(selected['ballot']['proposer'] in voters, 'selected originals proposer')
    offset = 0; result = []
    for ref in refs:
        need(len(raw)-offset >= 48, 'selected originals missing frame')
        length = 48 + struct.unpack('>I', raw[offset+12:offset+16])[0]
        need(48 < length <= 16384 and length <= len(raw)-offset, 'selected originals frame bound')
        frame = raw[offset:offset+length]; offset += length
        basis = f.decode(frame, 'records', 'BASIS', selected['root'])
        need(ref == dict(voter=basis['voter'], basisId=basis['basisId'], basisDigest=digest(frame)), 'selected originals reference')
        need(all(basis[k] == selected[k] for k in ('root', 'view', 'ballot')), 'selected originals decision')
        cut = basis['cut']
        need(authority(basis['root'], cut['view']) == basis['view'] and cut['index'] <= selected['cut']['index'], 'selected originals cut')
        result.append(cut)
    need(offset == len(raw) and selected['cut'] in result, 'selected originals trailing/longest')
    return result


def retained(original, prefix):
    """Only the ORIGINAL selector-bound manifest chooses legacy vs retained-frame mode.

    Never infer optionality from the candidate output. The caller compares every
    output member against its independently projected inventory.
    """
    manifest_raw = original[prefix+'generation.gsr']; manifest = f.decode(manifest_raw, 'records', 'GENERATION')
    selector = f.decode(original['selector.gsr'], 'records', 'SELECTOR', manifest['root'])
    need(selector['digest'] == digest(manifest_raw) and selector['generation'] == manifest['generation']
         and selector['node'] == manifest['node'] and prefix == 'generations/'+manifest['generation']+'/', 'selected originals manifest authority')
    names = [r['path'] for r in manifest['files']]
    need(names == sorted(set(names)), 'selected originals manifest inventory')
    if FILE not in names:
        need(prefix+FILE not in original, 'selected originals unlisted member')
        return {}
    raw = original[prefix+FILE]; row = next(r for r in manifest['files'] if r['path'] == FILE)
    need(row == dict(path=FILE, size=len(raw), sha256=digest(raw)), 'selected originals manifest bytes')
    selected_raw = original[prefix+'selected.gsr']
    need(digest(selected_raw) == manifest['selection'], 'selected originals selection digest')
    cuts(raw, f.decode(selected_raw, 'records', 'SELECTED', manifest['root']))
    return {FILE: raw}


def recorded_mode(directory):
    value = json.loads((Path(directory)/'case.json').read_text()).get('selectedSourceFrames', False)
    need(type(value) is bool, 'selected originals recorded mode')
    return value

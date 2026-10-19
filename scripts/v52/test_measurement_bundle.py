import hashlib
import gzip
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from . import measurement_bundle as b
from .evidence import encoded
from scripts.v51 import performance_bundle as predecessor


class MeasurementBundleTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def archive(self,items):
        path=self.root/'input.tar.gz'
        with tarfile.open(path,'w:gz',format=tarfile.USTAR_FORMAT) as out:
            for info,data in items:out.addfile(info,io.BytesIO(data))
        return path

    def file(self,name,data):
        info=tarfile.TarInfo(name);info.size=len(data);return info,data

    def manifest(self,files):return self.file(b.INDEX,encoded({k:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for k,v in files.items()}))

    def test_more_than_old_file_ceiling_roundtrips_without_changing_old_ceiling(self):
        raw=self.root/'raw';raw.mkdir();(raw/'empty').mkdir();(raw/'Nested$Class.class').write_bytes(b'class fixture')
        for i in range(4001):(raw/f'{i}.bin').write_bytes(str(i).encode())
        self.assertEqual(4000,predecessor.LIMITS['files'])
        with self.assertRaisesRegex(ValueError,'evidence ceiling'):predecessor.members(raw)
        archive=self.root/'bundle.tar.gz';index=b.pack(raw,archive);target=b.unpack(archive,self.root/'unpacked')
        self.assertEqual(4002,len(index));self.assertEqual(index,b.inventory(target));self.assertTrue((target/'empty').is_dir())
        self.assertEqual(4000,predecessor.LIMITS['files'])

    def test_symlinks_traversal_and_conflicting_paths_reject(self):
        raw=self.root/'raw';raw.mkdir();(raw/'safe').write_bytes(b'safe');(raw/'link').symlink_to(raw/'safe')
        with self.assertRaisesRegex(ValueError,'symlink'):b.members(raw)
        for path in ('../escape','/absolute','a/../escape','a//x','./x','a\\x','x\n','x'*256):
            with self.subTest(path=path),self.assertRaises(ValueError):b.name(path)
        for relative in ('.','..',''):
            with self.assertRaises(ValueError):b.name(relative)
        value={k:dict(bytes=1,sha256='a'*64) for k in ('x','x/y')}
        with self.assertRaisesRegex(ValueError,'file/directory conflict'):b.validate_index(value)

    def test_unsupported_extensions_links_and_sparse_reject_before_body(self):
        for kind in (tarfile.XHDTYPE,tarfile.GNUTYPE_LONGNAME,tarfile.GNUTYPE_SPARSE,tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.FIFOTYPE):
            with self.subTest(kind=kind):
                info=tarfile.TarInfo('extension');info.type=kind;info.size=0
                archive=self.archive([(info,b'')])
                with self.assertRaisesRegex(ValueError,'extension/link type'):b.unpack(archive,self.root/('out-'+kind.hex()))

    def test_extension_body_is_rejected_before_reading_its_claimed_gigabyte(self):
        info=tarfile.TarInfo('extension');info.type=tarfile.XHDTYPE;info.size=1<<30
        archive=self.root/'oversized-extension.tar.gz'
        with gzip.open(archive,'wb') as out:out.write(info.tobuf(format=tarfile.USTAR_FORMAT)+b'\0'*1024)
        with self.assertRaisesRegex(ValueError,'extension/link type'):b.unpack(archive,self.root/'out')

    def test_missing_extra_changed_and_duplicate_files_reject(self):
        good=self.file('a',b'one');first=self.manifest({'a':b'one'})
        variants=[([first],'missing archive member'),([first,good,good],'duplicate bundle member'),
                  ([first,self.file('a',b'two')],'member digest'),([first,self.file('b',b'one')],'unlisted/changed archive member'),
                  ([good],'first inventory')]
        for number,(items,reason) in enumerate(variants):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):b.unpack(self.archive(items),self.root/f'out-{number}')

    def test_inventory_and_expansion_limits_reject_before_extracting_payload(self):
        first=self.manifest({'a':b'one'});info=tarfile.TarInfo('a');info.size=3
        limits=dict(b.LIMITS,member=2)
        with patch.object(b,'LIMITS',limits),self.assertRaisesRegex(ValueError,'inventory member bound'):
            b.unpack(self.archive([first,(info,b'one')]),self.root/'out')
        self.assertFalse((self.root/'out/a').exists())
        with patch.object(b,'LIMITS',dict(b.LIMITS,inventory=2)),self.assertRaisesRegex(ValueError,'expanded evidence ceiling'):
            b.unpack(self.archive([first]),self.root/'out-two')

    def test_cannot_overwrite_target_or_pack_inside_source(self):
        raw=self.root/'raw';raw.mkdir();(raw/'file').write_bytes(b'data')
        with self.assertRaisesRegex(ValueError,'fresh sibling'):b.pack(raw,raw/'inside.tar.gz')
        archive=self.root/'bundle.tar.gz';b.pack(raw,archive)
        with self.assertRaisesRegex(ValueError,'fresh sibling'):b.pack(raw,archive)
        with self.assertRaisesRegex(ValueError,'fresh extraction'):b.unpack(archive,raw)
        link=self.root/'linked';link.symlink_to(raw,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'root type'):b.pack(link,self.root/'other.tar.gz')

    def test_mutated_download_and_authority_inventory_are_not_trusted(self):
        raw=self.root/'raw';raw.mkdir();(raw/'node-1').mkdir();(raw/'node-1/manifest.gsr').write_bytes(b'original')
        archive=self.root/'bundle.tar.gz';b.pack(raw,archive);copy=b.unpack(archive,self.root/'out')
        location=b.EvidenceLocation(copy,raw)
        with patch.object(b.storage,'_inspect',return_value='INSPECTED') as inspect:
            self.assertEqual('INSPECTED',location.inspect(copy/'node-1'));self.assertEqual(raw/'node-1',inspect.call_args.args[-1])
        (copy/'node-1/manifest.gsr').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'authority inventory differs'):location.inspect(copy/'node-1')
        with self.assertRaisesRegex(ValueError,'inventory/hash differs'):b.EvidenceLocation(copy,raw)


if __name__=='__main__':unittest.main()

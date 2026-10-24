"""Prevent invalid originals and malformed images from passing qualification."""
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import bootstrap_publication_evidence as m


class BootstrapPublicationEvidenceTest(unittest.TestCase):
    def test_invalid_original_stops_before_negative_generation(self):
        with patch.object(m,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(m.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'invalid original'):m.qualify('missing')
            validate.assert_called_once();copytree.assert_not_called()

    def test_missing_or_linked_evidence_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'missing'
            with self.assertRaises(ValueError):m.validate(path)
            real=Path(tmp)/'real';real.mkdir();path.symlink_to(real,target_is_directory=True)
            with self.assertRaises(ValueError):m.validate(path)

    def image(self,parts=(b'checkpoint',b'manifest',b'metadata')):
        payload=b''.join(struct.pack('>I',len(p))+p for p in parts)
        return struct.pack('>4sHHI',b'GSAI',1,3,len(payload))+payload

    def test_image_header_version_size_and_trailing_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=self.image()
            for bad in (b'',raw[:12],b'WRNG'+raw[4:],raw[:6]+b'\x00\x02'+raw[8:],raw+b'x',self.image((b'a',b'b',b'c',b'd'))):
                with self.subTest(raw=bad),self.assertRaises(ValueError):m.typed_image(Path(tmp),bad)

    def test_zero_or_excessive_member_size_is_rejected_before_reading_members(self):
        with patch.object(m.c,'inventory') as inventory:
            for size in (0,2**32-1):
                raw=self.image();bad=raw[:12]+struct.pack('>I',size)+raw[16:]
                with self.subTest(size=size),self.assertRaises(ValueError):m.typed_image(Path('absent'),bad)
            inventory.assert_not_called()

    def test_typed_inspection_must_equal_all_three_original_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);parts=(b'checkpoint',b'manifest',b'metadata')
            for name,raw in zip(('gse-backup-checkpoint','gse-backup-manifest','gse-backup-metadata'),parts):(path/name).write_bytes(raw)
            m.typed_image(path,self.image(parts))
            (path/'gse-backup-checkpoint').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'exact typed inspection'):m.typed_image(path,self.image(parts))

    def test_snapshot_cannot_accept_extra_voter_or_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'stage').mkdir();(path/'stage/node-1').mkdir();(path/'stage/node-1/record').write_bytes(b'a')
            m.match(path,'stage',{'node-1':{'record':b'a'}})
            (path/'stage/node-2').mkdir()
            with self.assertRaises(ValueError):m.match(path,'stage',{'node-1':{'record':b'a'}})


if __name__=='__main__':unittest.main()

"""Artifact regression: external, dangling and cyclic fixture links stay metadata."""
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from .provider_artifacts import pack


class ProviderArtifactTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root/'v51-cloud-provider'; self.source.mkdir()
        self.output = self.root/'provider.tar.gz'

    def test_external_directory_dangling_and_cyclic_links_are_not_traversed(self):
        outside = self.root/'outside'; outside.mkdir(); (outside/'never-upload').write_bytes(b'foreign host content')
        fixture = self.source/'run/root-receiver/symlink-parent/rootfs/var/lib'; fixture.mkdir(parents=True)
        link = fixture/'gse-v51-helper'; link.symlink_to(outside)
        (self.source/'dangling').symlink_to(self.root/'missing')
        (self.source/'cycle').symlink_to(self.source)
        (self.source/'receipt.json').write_bytes(b'{"status":"PASS"}\n')
        outside.chmod(0)
        try: pack(self.source, self.output)
        finally: outside.chmod(0o700)
        with tarfile.open(self.output, 'r:gz') as archive:
            name = 'v51-cloud-provider/run/root-receiver/symlink-parent/rootfs/var/lib/gse-v51-helper'
            entry = archive.getmember(name)
            self.assertTrue(entry.issym()); self.assertEqual(entry.linkname, str(outside))
            self.assertTrue(archive.getmember('v51-cloud-provider/dangling').issym())
            self.assertTrue(archive.getmember('v51-cloud-provider/cycle').issym())
            self.assertFalse(any('never-upload' in member.name for member in archive.getmembers()))
            self.assertEqual(archive.extractfile('v51-cloud-provider/receipt.json').read(), b'{"status":"PASS"}\n')
        self.assertTrue(link.is_symlink()); self.assertEqual((outside/'never-upload').read_bytes(), b'foreign host content')

    def test_failed_collection_publishes_no_partial_archive(self):
        with patch.object(tarfile.TarFile, 'add', side_effect=PermissionError('fixture inaccessible')):
            with self.assertRaises(PermissionError): pack(self.source, self.output)
        self.assertFalse(self.output.exists()); self.assertEqual(list(self.root.glob('.provider-evidence-*')), [])

    def test_missing_linked_root_internal_output_and_overwrite_rejected(self):
        with self.assertRaises(ValueError): pack(self.root/'missing', self.output)
        alias = self.root/'alias'; alias.symlink_to(self.source)
        with self.assertRaises(ValueError): pack(alias, self.output)
        with self.assertRaises(ValueError): pack(self.source, self.source/'archive.tar.gz')
        self.output.write_bytes(b'original')
        with self.assertRaises(FileExistsError): pack(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), b'original')


if __name__ == '__main__': unittest.main()

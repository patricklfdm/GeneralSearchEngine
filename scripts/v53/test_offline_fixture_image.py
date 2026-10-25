import unittest
from . import offline_fixture_image as image


class OfflineFixtureImageTest(unittest.TestCase):
    def test_castagnoli_check_value_and_empty(self):
        self.assertEqual(0,image.crc32c(b''))
        self.assertEqual(0xe3069283,image.crc32c(b'123456789'))

    def test_table_checksum_matches_independent_bitwise_decoder(self):
        for raw in (bytes(range(256)),bytes(range(255,-1,-1))*17,b'\x00'*1024,b'\xff'*1025):
            self.assertEqual(image.core.crc32c(raw),image.crc32c(raw))

    def test_checked_cursor_rejects_mutation_and_short_member(self):
        raw=image.core.checked(bytes(range(128)))
        cursor=image.uncheck(raw,64,'fixture');self.assertEqual(bytes(range(128)),cursor.take(128));cursor.finish()
        for bad in (raw[:63],raw[:-1],raw[:-4]+b'\0'*4,bytes([raw[0]^1])+raw[1:]):
            with self.assertRaises(ValueError):image.uncheck(bad,64,'fixture')

    def test_bound_checks_precede_member_parsing(self):
        import struct
        for size in (0,2**32-1):
            raw=struct.pack('>4sHHII',b'GSAI',1,3,16,size)+b'\0'*12
            with self.assertRaisesRegex(ValueError,'image member size'):image.image_members(raw)


if __name__=='__main__':unittest.main()

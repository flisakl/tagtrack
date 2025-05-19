from .helper import TestHelper
from mutagen import File

from tagtrack.tags import ID3Editor


class TestEditors(TestHelper):
    def test_metadata_are_read_properly_from_mp3_file(self):
        f = File(self.temp_file('song.mp3', 'audio/mpeg'))

        meta = ID3Editor().read_metadata(f)

        expected = {'name': 'Why Judy Why', 'year': 1970, 'number': 1}
        self.assertJSONMatchesDict(meta, expected)
        self.assertTrue(meta["duration"])
        self.assertTrue(meta['album']["image"])
        self.assertEqual(meta['album']["name"], "Cold Spring Harbor")
        self.assertEqual(meta['album']["year"], 1970)
        self.assertEqual(meta['album']["artist"], "Billy Joel")
        self.assertEqual("Billy Joel", meta['artists'][0]["name"])
        self.assertEqual("Kaneko Ayano", meta['artists'][1]["name"])
        self.assertTrue(meta['artists'][0]["image"])
        self.assertTrue(meta['artists'][1]["image"])

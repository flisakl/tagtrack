from .helper import TestHelper
from mutagen import File

from tagtrack.tags import ID3Editor, Editor
from tagtrack.models import Song


class TestEditors(TestHelper):
    async def test_song_is_properly_converted_to_metadata(self):
        aa = await self.create_artist('Billy Joel', image=self.temp_file())
        artists = [
            aa,
            await self.create_artist('Kaneko Ayano', image=self.temp_file()),
            await self.create_artist('Johnny Cash', image=self.temp_file()),
        ]
        album = await self.create_album(aa, 'Test Album', 'Metal', 1970, self.temp_file())
        song = await self.create_song(
            self.temp_file('song.mp3', 'audio/mpeg'),
            artists=artists, image=self.temp_file(),
            album=album
        )
        song = await Song.objects.prefetch_related('artists').select_related(
            'album__artist').aget(pk=song.pk)

        meta = Editor().song_to_metadata(song)

        # Song properties
        self.assertEqual(meta['name'], song.name)
        self.assertEqual(meta['year'], song.year)
        self.assertEqual(meta['genre'], song.genre)
        self.assertEqual(meta['number'], song.number)
        self.assertIn('image', meta.keys())
        self.assertIn('album', meta.keys())
        # Album properties
        alb = meta['album']
        self.assertEqual(alb['name'], album.name)
        self.assertEqual(alb['genre'], album.genre)
        self.assertEqual(alb['year'], album.year)
        self.assertEqual(alb['artist'], aa.name)
        self.assertIn('image', alb.keys())
        # Artists
        art = meta['artists']
        self.assertEqual(len(art), 3)
        self.assertEqual(art[0]['name'], artists[0].name)
        self.assertEqual(art[1]['name'], artists[1].name)
        self.assertEqual(art[2]['name'], artists[2].name)

    def test_metadata_are_read_properly_from_mp3_file(self):
        f = File(self.temp_file('song.mp3', 'audio/mpeg'))

        meta = ID3Editor().read_metadata(f)

        expected = {'name': 'Why Judy Why', 'year': 1970, 'number': 1}
        self.assertJSONMatchesDict(meta, expected)
        self.assertTrue(meta["duration"])
        self.assertTrue(meta['album']["image"])
        self.assertEqual(meta['album']["name"], "Cold Spring Harbor")
        self.assertEqual(meta['album']["year"], 1970)
        self.assertEqual(meta['album']["artist"]['name'], "Billy Joel")
        self.assertEqual("Billy Joel", meta['artists'][0]["name"])
        self.assertEqual("Kaneko Ayano", meta['artists'][1]["name"])
        self.assertTrue(meta['artists'][0]["image"])
        self.assertTrue(meta['artists'][1]["image"])

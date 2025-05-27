from .helper import TestHelper
from mutagen import File
from mutagen.mp4 import MP4

from tagtrack.tags import ID3Editor, Editor, MP4Editor
from tagtrack.models import Song


class TestEditors(TestHelper):
    async def prepare_song(self, fname: str = "song.mp3", mime: str = "audio/mpeg") -> Song:
        aa = await self.create_artist('Billy Joel', image=self.temp_file())
        artists = [
            aa,
            await self.create_artist('Kaneko Ayano', image=self.temp_file()),
            await self.create_artist('Johnny Cash', image=self.temp_file()),
        ]
        album = await self.create_album(aa, 'Test Album', 'Metal', 1970, self.temp_file())
        song = await self.create_song(
            self.temp_file(fname, mime),
            'Test Song Name',
            'Metal',
            artists=artists, image=self.temp_file(),
            album=album
        )
        song = await Song.objects.prefetch_related('artists').select_related(
            'album__artist').aget(pk=song.pk)
        return song

    async def test_song_is_properly_converted_to_metadata(self):
        song = await self.prepare_song()
        e = Editor()
        e.song_to_metadata(song)
        meta = e.meta

        # Song properties
        self.assertEqual(meta['name'], song.name)
        self.assertEqual(meta['year'], song.year)
        self.assertEqual(meta['genre'], song.genre)
        self.assertEqual(meta['number'], song.number)
        self.assertIn('image', meta.keys())
        self.assertIn('album', meta.keys())
        # Album properties
        alb = meta['album']
        self.assertEqual(alb['name'], song.album.name)
        self.assertEqual(alb['artist'], song.album.artist.name)
        self.assertIn('image', alb.keys())
        # Artists
        art = meta['artists']
        self.assertEqual(len(art), 3)
        artists = song.artists.all()
        self.assertEqual(art[0]['name'], artists[0].name)
        self.assertEqual(art[1]['name'], artists[1].name)
        self.assertEqual(art[2]['name'], artists[2].name)

    def check_metadata_reading(self, meta, check_artist_images: bool = True):
        expected = {'name': 'Why Judy Why', 'year': 1970, 'number': 1}
        self.assertJSONMatchesDict(meta, expected)
        self.assertTrue(meta["duration"])
        self.assertTrue(meta['album']["image"])
        self.assertEqual(meta['album']["name"], "Cold Spring Harbor")
        self.assertEqual(meta['album']["artist"], "Billy Joel")
        self.assertEqual("Billy Joel", meta['artists'][0]["name"])
        self.assertEqual("Kaneko Ayano", meta['artists'][1]["name"])
        if check_artist_images:
            self.assertTrue(meta['artists'][0]["image"])
            self.assertTrue(meta['artists'][1]["image"])

    def check_metadata_writing(self, read, song):
        # Song properties
        self.assertEqual(read['name'], song.name)
        self.assertEqual(read['year'], song.year)
        self.assertEqual(read['genre'], song.genre)
        self.assertEqual(read['number'], song.number)
        self.assertIn('album', read.keys())
        # Album properties
        alb = read['album']
        self.assertEqual(alb['name'], song.album.name)
        self.assertEqual(alb['artist'], song.album.artist.name)
        self.assertIn('image', alb.keys())
        # Artists
        art = read['artists']
        self.assertEqual(len(art), 3)
        artists = song.artists.all()
        self.assertEqual(art[0]['name'], artists[0].name)
        self.assertEqual(art[1]['name'], artists[1].name)
        self.assertEqual(art[2]['name'], artists[2].name)

    def test_metadata_are_read_properly_from_mp3_file(self):
        f = File(self.temp_file('song.mp3', 'audio/mpeg'))
        editor = ID3Editor()

        meta = editor.read(f)

        self.check_metadata_reading(meta)

    async def test_metadata_are_written_properly_to_mp3_files(self):
        song = await self.prepare_song()
        e = Editor()
        e.song_to_metadata(song)
        meta = e.meta
        editor = ID3Editor()

        editor.write(song.file, meta)

        read = editor.read(File(song.file))
        self.check_metadata_writing(read, song)

    async def test_metadata_are_read_properly_from_mp4_file(self):
        f = MP4(self.temp_file('song.mp4', 'video/mp4'))
        editor = MP4Editor()
        meta = editor.read(f)

        self.check_metadata_reading(meta, check_artist_images=False)

    async def test_metadata_are_written_properly_to_mp4_files(self):
        song = await self.prepare_song("song.mp4", "audio/mpeg")
        editor = MP4Editor()

        editor.write(song=song)

        read = editor.read(File(song.file))
        self.check_metadata_writing(read, song)

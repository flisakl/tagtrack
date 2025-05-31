import shutil
from os import path
from django.test import TestCase
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.conf import settings

from tagtrack.models import Artist, Album, Song


class TestHelper(TestCase):

    def temp_file(self, name: str = 'image.jpg', mime: str = 'image/jpeg',
                  upload_filename: str = None):
        fname = upload_filename if upload_filename else name
        fp = path.join(path.dirname(__file__), 'test_files/', name)
        with open(fp, 'rb') as file:
            fdata = file.read()
            tuf = TemporaryUploadedFile(fname, mime, len(fdata), 'utf-8')
            tuf.file.write(fdata)
            tuf.file.seek(0)
        return tuf

    def file_exists(self, dir: str, fname: str):
        fpath = path.join(settings.MEDIA_ROOT, dir, fname)
        return path.isfile(fpath)

    @classmethod
    def tearDownClass(cls):
        dirnames = ['artists', 'albums', 'songs', 'singles']
        paths = [f"{path.join(settings.MEDIA_ROOT, x)}" for x in dirnames]
        for p in paths:
            shutil.rmtree(p, ignore_errors=True)

    async def create_artist(
        self,
        name: str = 'Billy Joel',
        image: TemporaryUploadedFile = None,
        albums: list[Album] = []
    ):
        obj = await Artist.objects.acreate(name=name, image=image)
        if albums:
            await obj.albums.aset(albums)
        return obj

    async def create_album(
        self,
        artist: Artist,
        name: str = 'Cold Spring Harbor',
        genre: str = 'Rock',
        year: int = 1970,
        image: TemporaryUploadedFile = None,
        songs: list[Song] = []
    ):
        obj = await Album.objects.acreate(
            name=name, image=image, artist=artist,
            genre=genre, year=year
        )
        if songs:
            await obj.songs.aset(songs)
        return obj

    async def create_song(
        self,
        file: TemporaryUploadedFile,
        name: str = 'Why Judy Why',
        genre: str = 'Rock',
        year: int = 1970,
        duration: int = 180,
        number: int = 1,
        artists: list[Artist] = [],
        image: TemporaryUploadedFile = None,
        album: Album = None
    ):
        obj = await Song.objects.acreate(
            name=name, image=image, number=number,
            album=album, file=file, genre=genre, year=year, duration=duration
        )

        if artists:
            await obj.artists.aset(artists)
        return obj

    async def create_artists(self):
        data = [
            {'name': 'Billy Joel'},
            {'name': 'Kaneko Ayano'},
            {'name': 'Pearl Jam'},
            {'name': 'Ghost'},
            {'name': 'Metallica'},
            {'name': 'Pantera'},
            {'name': 'System of a Down'},
            {'name': 'Iron Maiden'},
            {'name': 'Slipknot'},
            {'name': 'Buckethead'},
        ]
        artists = [Artist(**d) for d in data]
        return await Artist.objects.abulk_create(artists)

    async def create_albums(self):
        a = await self.create_artists()
        data = [
            {'genre': 'Piano Rock', 'year': 1970, 'artist': a[0], 'name': 'Cold Spring Harbor'},
            {'genre': 'Soft Rock', 'year': 1973, 'artist': a[0], 'name': 'Piano Man'},
            {'genre': 'J-pop', 'year': 2019, 'artist': a[1], 'name': 'Sansan'},
            {'genre': 'Alt Rock', 'year': 1996, 'artist': a[2], 'name': 'No Code'},
            {'genre': 'Alt Rock', 'year': 1998, 'artist': a[2], 'name': 'Yield'},
            {'genre': 'Pop rock', 'year': 2022, 'artist': a[3], 'name': 'Impera'},
            {'genre': 'Pop rock', 'year': 2015, 'artist': a[3], 'name': 'Meliora'},
            {'genre': 'Pop rock', 'year': 2010, 'artist': a[3], 'name': 'Opus Eponymous'},
            {'genre': 'Metal', 'year': 1986, 'artist': a[4], 'name': 'Master of Puppets'},
            {'genre': 'Metal', 'year': 2003, 'artist': a[4], 'name': 'St. Anger'},
        ]
        objs = [Album(**d) for d in data]
        return await Album.objects.abulk_create(objs)

    async def create_songs(self, albums: list[Album] = None):
        a = albums if albums else await self.create_albums()
        data = [
            {'album': a[0], 'name': 'Why Judy Why', 'year': 1970, 'genre': 'Rock', 'duration': 350},
            {'album': a[6], 'name': 'Spirit', 'year': 2015, 'genre': 'Hard Rock', 'duration': 315},
            {'album': a[6], 'name': 'He Is', 'year': 2015, 'genre': 'Hard Rock', 'duration': 253},
            {'album': a[1], 'name': 'Piano Man', 'year': 1973, 'genre': 'Soft Rock', 'duration': 250},
            {'album': a[8], 'name': 'Battery', 'year': 1986, 'genre': 'Metal', 'duration': 312},
            {'album': a[8], 'name': 'Master of Puppets', 'year': 1986, 'genre': 'Metal', 'duration': 515},
            {'album': a[8], 'name': 'Disposable Heroes', 'year': 1986, 'genre': 'Metal', 'duration': 497},
            {'album': a[2], 'name': 'Hana Hiraku Made', 'year': 2019, 'genre': 'J-pop', 'duration': 160},
            {'album': a[2], 'name': 'Akegata', 'year': 2019, 'genre': 'J-pop', 'duration': 197},
            {'album': a[3], 'name': 'Sometimes', 'year': 1996, 'genre': 'Alt Rock', 'duration': 161}
        ]
        for idx, x in enumerate(data):
            x['file'] = self.temp_file('song.mp3', 'audio/mpeg', f'song_{idx}.mp3')
            x['number'] = 1
        objs = [Song(**d) for d in data]
        ret = await Song.objects.abulk_create(objs)
        SongArtist = Song.artists.through
        data = [
            {'artist_id': 1, 'song_id': 1},
            {'artist_id': 4, 'song_id': 2},
            {'artist_id': 4, 'song_id': 3},
            {'artist_id': 1, 'song_id': 4},
            {'artist_id': 5, 'song_id': 5},
            {'artist_id': 5, 'song_id': 6},
            {'artist_id': 5, 'song_id': 7},
            {'artist_id': 2, 'song_id': 8},
            {'artist_id': 2, 'song_id': 9},
            {'artist_id': 3, 'song_id': 10},
        ]
        await SongArtist.objects.abulk_create([SongArtist(**d) for d in data])
        return ret

    def assertJSONMatchesDict(self, json: dict, data: dict):
        for key, value in data.items():
            self.assertEqual(json[key], value)

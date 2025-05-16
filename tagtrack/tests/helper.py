import shutil
from os import path
from django.test import TestCase
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.conf import settings

from tagtrack.models import Artist, Album, Song


class TestHelper(TestCase):
    def load_file(self, path: str, mode: str = 'rb'):
        return open(path, mode)

    def temp_file(self, name: str = 'image.jpg', mime: str = 'image/jpeg',
                  upload_filename: str = None):
        fname = upload_filename if upload_filename else name
        tuf = TemporaryUploadedFile(fname, mime, 0, 'utf-8')
        fp = path.join(path.dirname(__file__), name)
        file = self.load_file(fp)
        tuf.file.write(file.read())
        file.close()
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
        obj = await Album.objects.acreate(name=name, image=image)
        if songs:
            await obj.songs.aset(songs)
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

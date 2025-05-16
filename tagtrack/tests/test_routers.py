from ninja.testing import TestAsyncClient

from tagtrack.routers import artists_router, albums_router, songs_router
from tagtrack.models import Artist, Album, Song
from .helper import TestHelper


class TestSongRouter(TestHelper):
    def setUp(self):
        self.client = TestAsyncClient(songs_router)

    async def test_song_can_be_added(self):
        artist = await Artist.objects.acreate(name='Squire Tuck')
        album = await Album.objects.acreate(
            name='Squire Tuck Soundtracks for the Soul',
            artist=artist
        )
        data = {
            'name': 'Yearning For Better Days',
            'duration': 166, 'genre': 'Instrumental', 'year': 2018,
            'number': 6, 'album_id': album.pk, 'artist_ids': f'{artist.pk}'
        }
        files = {
            'image': self.temp_file(),
            'file': self.temp_file('song.mp3', mime='audio/mpeg')
        }

        response = await self.client.post('', data=data, FILES=files)
        json = response.json()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, await Song.objects.acount())
        self.assertEqual(json['name'], data['name'])
        self.assertEqual(json['album']['name'], album.name)
        self.assertEqual(json['artists'][0]['name'], artist.name)

    async def test_songs_can_be_filtered(self):
        artist = await Artist.objects.acreate(name='billy joel')
        adata = [
            {'name': 'Cold Spring Harbor', 'artist_id': artist.pk},
            {'name': 'Piano Man', 'artist_id': artist.pk},
            {'name': 'Atilla', 'artist_id': artist.pk},
        ]
        albums = await Album.objects.abulk_create([Album(**d) for d in adata])
        sdata = [
            {'file': self.temp_file('song.mp3', 'audio/mpeg'), 'year': 1970, 'genre': 'Rock', 'duration': 350,
                'name': 'Why Judy Why', 'album_id': albums[0].pk},
            {'file': self.temp_file('song.mp3', 'audio/mpeg'), 'year': 1976, 'genre': 'Rock', 'duration': 120,
                'name': 'Tomorrow is Today', 'album_id': albums[0].pk},
            {'file': self.temp_file('song.mp3', 'audio/mpeg'), 'year': 1980, 'genre': 'Pop', 'duration': 100,
                'name': 'Piano Man', 'album_id': albums[1].pk},
            {'file': self.temp_file('song.mp3', 'audio/mpeg'), 'year': 2015, 'genre': 'Metal',
                'duration': 250, 'name': 'Sonne'},
            {'file': self.temp_file('song.mp3', 'audio/mpeg'), 'year': 2010, 'genre': 'Rock',
                'duration': 30, 'name': 'If you have ghosts'},
        ]
        await Song.objects.abulk_create([Song(**d) for d in sdata])
        rdata = [
            {'genre': 'roc'},
            {'name': 'tomorrow'},
            {'year_min': 1975, 'year_max': 1980},
            {'duration_max': 50},
            {'album_id': albums[0].pk},
            {'album_name': albums[1].name},
        ]

        r = [await self.client.get('', query_params=rd) for rd in rdata]
        j = [x.json() for x in r]

        self.assertTrue(all([x.status_code == 200 for x in r]))
        self.assertEqual(j[0]['count'], 3)
        self.assertEqual(j[1]['count'], 1)
        self.assertEqual(j[2]['count'], 2)
        self.assertEqual(j[3]['count'], 1)
        self.assertEqual(j[4]['count'], 2)
        self.assertEqual(j[5]['count'], 1)

    async def test_song_can_be_fetched(self):
        f = self.temp_file('song.mp3', 'audio/mpeg')
        art = await Artist.objects.acreate(name='Rammstein')
        alb = await Album.objects.acreate(name='Rosenrot', artist=art)
        obj = await Song.objects.acreate(duration=100, file=f, name='Test Song', album=alb)

        res = await self.client.get(f"/{obj.pk}")
        json = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['name'], 'Test Song')
        self.assertEqual(json['album']['name'], 'Rosenrot')

    async def test_song_can_be_updated(self):
        artist = await Artist.objects.acreate(name='Squire Tuck')
        album2 = await Album.objects.acreate(
            name='Test Album',
            artist=artist
        )
        album = await Album.objects.acreate(
            name='Squire Tuck Soundtracks for the Soul',
            artist=artist
        )

        song = await Song.objects.acreate(
            file=self.temp_file('song.mp3', upload_filename='old.mp3'),
            album_id=album.pk, name='Test Song', duration=160,
        )

        data = {
            'name': 'Yearning For Better Days',
            'duration': 166, 'genre': 'Instrumental', 'year': 2018,
            'number': 6, 'album_id': album2.pk, 'artist_ids': f'{artist.pk}'
        }

        files = {
            'image': self.temp_file(),
            'file': self.temp_file('song.mp3', mime='audio/mpeg'),
        }

        response = await self.client.patch(f'/{song.pk}', data=data, FILES=files)
        json = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, await Song.objects.acount())
        self.assertEqual(json['name'], data['name'])
        self.assertEqual(json['album']['name'], album2.name)
        self.assertEqual(json['artists'][0]['name'], artist.name)

    async def test_song_can_not_be_updated_with_non_existing_album(self):
        artist = await Artist.objects.acreate(name='Squire Tuck')
        album = await Album.objects.acreate(
            name='Squire Tuck Soundtracks for the Soul',
            artist=artist
        )
        obj = await Song.objects.acreate(
            file=self.temp_file('song.mp3', upload_filename='old.mp3'),
            album_id=album.pk, name='Test Song', duration=160,
        )
        files = {'image': self.temp_file()}
        data = {'name': 'New name', 'duration': 145, 'album_id': 5}

        res = await self.client.patch(f'/{obj.pk}', data=data, FILES=files)
        json = res.json()

        self.assertEqual(res.status_code, 422)
        self.assertIn('album_id', json['detail'][0]['loc'])

    async def test_song_can_be_deleted(self):
        artist = await Artist.objects.acreate(name='Squire Tuck')
        album = await Album.objects.acreate(
            name='Squire Tuck Soundtracks for the Soul',
            artist=artist
        )
        obj = await Song.objects.acreate(
            file=self.temp_file('song.mp3', upload_filename='old.mp3'),
            album_id=album.pk, name='Test Song', duration=160,
        )
        self.assertTrue(self.file_exists('songs', 'old.mp3'))

        res = await self.client.delete(f"/{obj.pk}")

        self.assertEqual(res.status_code, 204)
        self.assertFalse(self.file_exists('songs', 'old.mp3'))
        self.assertEqual(await Song.objects.acount(), 0)

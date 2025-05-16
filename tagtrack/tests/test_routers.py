from ninja.testing import TestAsyncClient

from tagtrack.routers import artists_router, albums_router, songs_router
from tagtrack.models import Artist, Album, Song
from .helper import TestHelper


class TestArtistRouter(TestHelper):
    def setUp(self):
        self.client = TestAsyncClient(artists_router)

    async def test_artist_can_be_created(self):
        data = {
            'name': 'Johnny Cash'
        }
        files = {'image': self.temp_file()}

        response = await self.client.post('', data=data, FILES=files)

        self.assertEqual(response.status_code, 201)
        obj = await Artist.objects.afirst()
        self.assertEqual(obj.name, data['name'])

    async def test_artist_can_not_create_2_artists_with_the_same_name(self):
        data = {
            'name': 'Johnny Cash'
        }
        files = {'image': self.temp_file()}
        await Artist.objects.acreate(name=data['name'])

        response = await self.client.post('', data=data, FILES=files)

        self.assertEqual(response.status_code, 422)

    async def test_artists_can_be_filtered(self):
        data = [
            {'name': 'Billy Joel'},
            {'name': 'Kaneko Ayano'},
            {'name': 'Pearl Jam'},
            {'name': 'Ghost'},
            {'name': 'Metallica'},
        ]
        objs = await Artist.objects.abulk_create([Artist(**d) for d in data])
        await Album.objects.abulk_create([
            Album(name='Cold Spring Harbor', artist=objs[0]),
            Album(name='Piano Man', artist=objs[0]),
            Album(name='St. Anger', artist=objs[4])
        ])

        r1 = await self.client.get('', query_params={'name': 'pearl'})
        r2 = await self.client.get('', query_params={'album_count': 1})

        self.assertTrue(all([r.status_code == 200 for r in [r1, r2]]))
        self.assertEqual(r1.json()['items'][0]['name'], 'Pearl Jam')
        self.assertEqual(r2.json()['items'][0]['name'], 'Billy Joel')

    async def test_artist_can_be_fetched(self):
        obj = await Artist.objects.acreate(name='Rammstein')
        await Album.objects.abulk_create([
            Album(name='Rosenrot', artist=obj),
            Album(name='Reise, Reise', artist=obj),
        ])

        res = await self.client.get(f"/{obj.pk}")
        json = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['name'], 'Rammstein')
        self.assertEqual(len(json['albums']), 2)

    async def test_artist_can_be_updated(self):
        obj = await Artist.objects.acreate(name='Romsetin')
        await Album.objects.abulk_create([
            Album(name='Rosenrot', artist=obj),
            Album(name='Reise, Reise', artist=obj),
        ])
        data = {'name': 'Rammstein'}

        res = await self.client.patch(f"/{obj.pk}", data=data)
        json = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['name'], 'Rammstein')

    async def test_artist_can_not_be_updated_with_existing_name(self):
        data = {
            'name': 'Johnny Cash'
        }
        files = {'image': self.temp_file()}
        await Artist.objects.acreate(name=data['name'])
        obj = await Artist.objects.acreate(name='Billy Joel')

        response = await self.client.patch(f'/{obj.pk}', data=data, FILES=files)

        self.assertEqual(response.status_code, 422)

    async def test_artist_can_be_deleted(self):
        f = self.temp_file(upload_filename='old.jpg')
        obj = await Artist.objects.acreate(name='Romsetin', image=f)
        self.assertTrue(self.file_exists('artists', 'old.jpg'))

        res = await self.client.delete(f"/{obj.pk}")

        self.assertEqual(res.status_code, 204)
        self.assertFalse(self.file_exists('artists', 'old.jpg'))
        self.assertEqual(await Artist.objects.acount(), 0)


class TestAlbumRouter(TestHelper):
    def setUp(self):
        self.client = TestAsyncClient(albums_router)

    async def test_album_can_be_created(self):
        artist = await Artist.objects.acreate(name='Billy Joel')
        data = {
            'name': 'Cold Spring Harbor',
            'genre': 'Rock',
            'year': 1970,
            'artist_id': artist.pk
        }
        files = {'image': self.temp_file()}

        response = await self.client.post('', data=data, FILES=files)

        self.assertEqual(response.status_code, 201)
        obj = await Album.objects.afirst()
        self.assertEqual(obj.name, data['name'])

    async def test_album_can_not_be_created_with_non_existing_artist(self):
        data = {
            'name': 'Cold Spring Harbor',
            'genre': 'Rock',
            'year': 1970,
            'artist_id': 1
        }
        files = {'image': self.temp_file()}

        response = await self.client.post('', data=data, FILES=files)

        self.assertEqual(response.status_code, 422)
        count = await Album.objects.acount()
        self.assertEqual(count, 0)

    async def test_album_name_must_be_unique_per_artist(self):
        artist = await Artist.objects.acreate(name='Billy Joel')
        data = {
            'name': 'Cold Spring Harbor',
            'genre': 'Rock',
            'year': 1970,
            'artist_id': artist.pk
        }
        await Album.objects.acreate(name=data['name'], artist=artist)
        files = {'image': self.temp_file()}

        response = await self.client.post('', data=data, FILES=files)

        self.assertEqual(response.status_code, 422)

    async def test_albums_can_be_filtered(self):
        adata = [
            {'name': 'Artist One'},
            {'name': 'Artist Two'},
            {'name': 'Funky man'},
            {'name': 'Bigman'},
        ]
        art = await Artist.objects.abulk_create([Artist(**d) for d in adata])

        await Album.objects.abulk_create([
            Album(year=1970, genre='Rock',
                  name='Rock above all', artist=art[0]),
            Album(year=1980, genre='Rock', name='Rock ballads', artist=art[0]),
            Album(year=1990, genre='Metal', name='Heavy riffs', artist=art[1]),
            Album(year=2010, genre='Metal',
                  name='Uncomprehensible leads', artist=art[2]),
            Album(year=2020, genre='Hip-Hop',
                  name='Gangsta Life', artist=art[3]),
        ])

        r1 = await self.client.get('', query_params={'name': 'rock'})
        r2 = await self.client.get('', query_params={'artist_id': art[0].pk, 'name': 'rock'})
        r3 = await self.client.get('', query_params={'year_min': 2015})
        r4 = await self.client.get('', query_params={'genre': 'metal'})
        r5 = await self.client.get('', query_params={'artist_name': 'funky'})

        self.assertTrue(all([r.status_code == 200 for r in [r1, r2, r3, r4]]))
        self.assertEqual(len(r1.json()['items']), 2)
        self.assertEqual(r2.json()['items'][0]['name'], 'Rock above all')
        self.assertEqual(r3.json()['items'][0]['name'], 'Gangsta Life')
        self.assertEqual(len(r4.json()['items']), 2)
        self.assertEqual(len(r5.json()['items']), 1)

    async def test_album_can_be_fetched(self):
        obj = await Artist.objects.acreate(name='Rammstein')
        albums = await Album.objects.abulk_create([
            Album(name='Rosenrot', artist=obj),
            Album(name='Reise, Reise', artist=obj),
        ])

        res = await self.client.get(f"/{albums[0].pk}")
        json = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['name'], 'Rosenrot')

    async def test_album_can_be_updated(self):
        art = await Artist.objects.acreate(name='Rammstein')
        obj = await Album.objects.acreate(name='bad name', artist=art)
        data = {'name': 'Good name', 'year': 1990,
                'genre': 'Metal', 'artist_id': art.pk}

        res = await self.client.patch(f"/{obj.pk}", data=data)
        json = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['name'], data['name'])
        self.assertEqual(json['year'], data['year'])
        self.assertEqual(json['genre'], data['genre'])

    async def test_album_can_not_be_updated_with_non_existing_author(self):
        art = await Artist.objects.acreate(name='Rammstein')
        obj = await Album.objects.acreate(name='Good name', artist=art)
        obj = await Album.objects.acreate(name='bad name', artist=art)
        data = {'name': 'Good name', 'year': 1990,
                'genre': 'Metal', 'artist_id': art.pk}

        res = await self.client.patch(f"/{obj.pk}", data=data)

        self.assertEqual(res.status_code, 422)

    async def test_album_can_not_be_updated_with_non_existing_author(self):
        art = await Artist.objects.acreate(name='Rammstein')
        obj = await Album.objects.acreate(name='bad name', artist=art)
        data = {'name': 'Good name', 'year': 1990,
                'genre': 'Metal', 'artist_id': 10}

        res = await self.client.patch(f"/{obj.pk}", data=data)

        self.assertEqual(res.status_code, 422)

    async def test_album_can_be_deleted(self):
        f = self.temp_file(upload_filename='old.jpg')
        art = await Artist.objects.acreate(name='Rammstein')
        obj = await Album.objects.acreate(name='Romsetin', image=f, artist=art)
        self.assertTrue(self.file_exists('albums', 'old.jpg'))

        res = await self.client.delete(f"/{obj.pk}")

        self.assertEqual(res.status_code, 204)
        self.assertFalse(self.file_exists('albums', 'old.jpg'))
        self.assertEqual(await Album.objects.acount(), 0)


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

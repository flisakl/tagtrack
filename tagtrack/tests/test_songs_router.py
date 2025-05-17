from ninja.testing import TestAsyncClient
from .helper import TestHelper

from tagtrack.routers import songs_router
from tagtrack.models import Artist, Album, Song


class TestSongRouter(TestHelper):
    def setUp(self):
        self.client = TestAsyncClient(songs_router)

    async def test_song_can_be_added(self):
        artist = await self.create_artist(name='Squire Tuck')
        a2 = await self.create_artist(name='Octopus')
        album = await self.create_album(
            name='Squire Tuck Soundtracks for the Soul', artist=artist)
        data = {
            'name': 'Yearning For Better Days',
            'duration': 166, 'genre': 'Instrumental', 'year': 2018,
            'number': 6, 'album_id': album.pk,
            'artist_ids': f'{artist.pk},{a2.pk}'
        }
        files = {
            'image': self.temp_file(),
            'file': self.temp_file('song.mp3', mime='audio/mpeg')}

        response = await self.client.post('', data=data, FILES=files)
        json = response.json()

        del data['album_id']
        del data['artist_ids']
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, await Song.objects.acount())
        self.assertJSONMatchesDict(json, data)
        self.assertEqual(json['album']['name'], album.name)
        self.assertEqual(json['artists'][0]['name'], artist.name)
        self.assertEqual(json['artists'][1]['name'], a2.name)

    async def test_songs_can_be_filtered(self):
        albums = await self.create_albums()
        await self.create_songs(albums)
        rdata = [
            {'genre': 'roc'},
            {'name': 'judy'},
            {'year_min': 1970, 'year_max': 1980},
            {'duration_max': 200},
            {'album_id': albums[8].pk},
            {'album_name': albums[1].name},
        ]

        r = [await self.client.get('', query_params=rd) for rd in rdata]
        j = [x.json() for x in r]

        self.assertTrue(all([x.status_code == 200 for x in r]))
        self.assertEqual(j[0]['count'], 5)
        self.assertEqual(j[1]['count'], 1)
        self.assertEqual(j[2]['count'], 2)
        self.assertEqual(j[3]['count'], 3)
        self.assertEqual(j[4]['count'], 3)
        self.assertEqual(j[5]['count'], 1)

    async def test_song_can_be_fetched(self):
        f = self.temp_file('song.mp3', 'audio/mpeg')
        art = await self.create_artist(name='Rammstein')
        alb = await self.create_album(name='Rosenrot', artist=art)
        obj = await self.create_song(f, album=alb, artists=[art])

        res = await self.client.get(f"/{obj.pk}")
        json = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['name'], obj.name)
        self.assertEqual(json['album']['name'], alb.name)
        self.assertEqual(json['artists'][0]['name'], art.name)

    async def test_song_can_be_updated(self):
        artist = await self.create_artist(name='Squire Tuck')
        album2 = await self.create_album(artist, name='Test Album')
        album = await self.create_album(artist, name='Soundtrack for the Soul')
        f = self.temp_file('song.mp3', upload_filename='old.mp3')
        f2 = self.temp_file(upload_filename='old.jpg')
        song = await self.create_song(f, album=album, image=f2)
        data = {
            'name': 'Yearning For Better Days',
            'duration': 166, 'genre': 'Instrumental', 'year': 2018,
            'number': 6, 'album_id': album2.pk, 'artist_ids': f'{artist.pk}'
        }
        f = {
            'image': self.temp_file(),
            'file': self.temp_file('song.mp3', mime='audio/mpeg'),
        }
        self.assertTrue(self.file_exists('songs', 'old.mp3'))
        self.assertTrue(self.file_exists('singles', 'old.jpg'))

        response = await self.client.patch(f'/{song.pk}', data=data, FILES=f)
        json = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, await Song.objects.acount())
        self.assertEqual(json['name'], data['name'])
        self.assertEqual(json['album']['name'], album2.name)
        self.assertEqual(json['artists'][0]['name'], artist.name)
        self.assertTrue(self.file_exists('songs', 'song.mp3'))
        self.assertTrue(self.file_exists('singles', 'image.jpg'))
        self.assertFalse(self.file_exists('songs', 'old.mp3'))
        self.assertFalse(self.file_exists('singles', 'old.jpg'))

    async def test_song_can_not_be_updated_with_non_existing_album(self):
        artist = await self.create_artist(name='Squire Tuck')
        album = await self.create_album(artist, name='Soundtrack for the Soul')
        f = self.temp_file('song.mp3', upload_filename='old.mp3')
        obj = await self.create_song(f, album=album)
        f = {'image': self.temp_file()}
        data = {'name': 'New name', 'duration': 145, 'album_id': 5}

        res = await self.client.patch(f'/{obj.pk}', data=data, FILES=f)
        json = res.json()

        self.assertEqual(res.status_code, 422)
        self.assertIn('album_id', json['detail'][0]['loc'])

    async def test_song_can_be_deleted(self):
        artist = await self.create_artist()
        album = await self.create_album(artist)
        f = self.temp_file('song.mp3', upload_filename='old.mp3')
        obj = await self.create_song(f, album=album)
        self.assertTrue(self.file_exists('songs', 'old.mp3'))

        res = await self.client.delete(f"/{obj.pk}")

        self.assertEqual(res.status_code, 204)
        self.assertFalse(self.file_exists('songs', 'old.mp3'))
        self.assertEqual(await Song.objects.acount(), 0)

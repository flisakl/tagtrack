from ninja.testing import TestAsyncClient
from .helper import TestHelper

from tagtrack.routers import albums_router
from tagtrack.models import Album


class TestRouter(TestHelper):
    def setUp(self):
        self.client = TestAsyncClient(albums_router)
        self.params = {
            'name': 'Cold Spring Harbor',
            'genre': 'Rock',
            'year': 1970,
        }

    async def test_album_can_be_created(self):
        artist = await self.create_artist()
        files = {'image': self.temp_file()}
        dt = self.params.copy()
        dt['artist_id'] = artist.pk

        response = await self.client.post('', dt, FILES=files)
        json = response.json()
        del dt['artist_id']

        self.assertEqual(response.status_code, 201)
        self.assertJSONMatchesDict(json, dt)

    async def test_album_can_not_be_created_with_non_existing_artist(self):
        dt = self.params.copy()
        dt['artist_id'] = 5
        files = {'image': self.temp_file()}

        response = await self.client.post('', dt, FILES=files)
        json = response.json()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(json['detail']), 1)
        self.assertIn('artist_id', json['detail'][0]['loc'])
        self.assertEqual(await Album.objects.acount(), 0)

    async def test_album_name_must_be_unique_per_artist(self):
        artist = await self.create_artist('Ghost')
        alb = await self.create_album(artist, 'Meliora')
        dt = self.params.copy()
        dt['name'], dt['artist_id'] = alb.name, artist.pk
        files = {'image': self.temp_file()}

        response = await self.client.post('', dt, FILES=files)
        json = response.json()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(json['detail']), 1)
        self.assertIn('name', json['detail'][0]['loc'])

    async def test_albums_can_be_filtered(self):
        albums = await self.create_albums()
        params = [
            {'name': 'master'},
            {'artist_id': albums[0].artist.pk, 'name': 'cold'},
            {'year_min': 2015},
            {'genre': 'metal'},
            {'artist_name': 'ghost'}
        ]

        res = [await self.client.get('', query_params=x) for x in params]
        json = [x.json() for x in res]

        self.assertTrue(all([r.status_code == 200 for r in res]))
        self.assertEqual(json[0]['count'], 1)
        self.assertEqual(json[0]['items'][0]['name'], 'Master of Puppets')
        self.assertEqual(json[1]['count'], 1)
        self.assertEqual(json[1]['items'][0]['name'], 'Cold Spring Harbor')
        self.assertEqual(json[2]['count'], 3)
        self.assertEqual(json[2]['items'][0]['name'], 'Sansan')
        self.assertEqual(json[2]['items'][1]['name'], 'Impera')
        self.assertEqual(json[2]['items'][2]['name'], 'Meliora')
        self.assertEqual(json[3]['count'], 2)
        self.assertEqual(json[4]['count'], 3)

    async def test_album_can_be_fetched(self):
        art = await self.create_artist()
        alb = await self.create_album(art)

        res = await self.client.get(f"/{alb.pk}")
        json = res.json()

        expected = {
            'name': alb.name,
            'genre': alb.genre,
            'year': alb.year,
            'artist': {
                'id': 1,
                'image': None,
                'name': art.name,
                'song_count': None,
                'album_count': None,
            }
        }
        self.assertEqual(res.status_code, 200)
        self.assertJSONMatchesDict(json, expected)

    async def test_album_can_be_updated(self):
        art = await self.create_artist('Rammstein')
        obj = await self.create_album(art, 'bad name')
        data = {'name': 'Good name', 'year': 1990,
                'genre': 'Metal', 'artist_id': art.pk}

        res = await self.client.patch(f"/{obj.pk}", data)
        json = res.json()

        del data['artist_id']
        self.assertEqual(res.status_code, 200)
        self.assertJSONMatchesDict(json, data)

    async def test_album_can_not_be_updated_with_non_existing_author(self):
        art = await self.create_artist('Rammstein')
        obj = await self.create_album(art, 'Bad name')
        data = {'name': 'Good name', 'year': 1990,
                'genre': 'Metal', 'artist_id': 15}

        res = await self.client.patch(f"/{obj.pk}", data=data)
        json = res.json()

        self.assertEqual(res.status_code, 422)
        self.assertEqual(len(json['detail']), 1)
        self.assertIn('artist_id', json['detail'][0]['loc'])

    async def test_can_not_update_album_when_album_name_is_taken(self):
        art = await self.create_artist('Rammstein')
        obj = await self.create_album(art, 'Meliora')
        obj2 = await self.create_album(art, 'Circe')
        data = {'name': obj2.name, 'year': 1990,
                'genre': 'Metal', 'artist_id': art.pk}

        res = await self.client.patch(f"/{obj.pk}", data)
        json = res.json()

        self.assertEqual(res.status_code, 422)
        self.assertEqual(len(json['detail']), 1)
        self.assertIn('name', json['detail'][0]['loc'])

    async def test_album_can_be_deleted(self):
        f = self.temp_file(upload_filename='old.jpg')
        art = await self.create_artist('Rammstein')
        obj = await self.create_album(art, 'Meliora', image=f)
        self.assertTrue(self.file_exists('albums', 'old.jpg'))

        res = await self.client.delete(f"/{obj.pk}")

        self.assertEqual(res.status_code, 204)
        self.assertFalse(self.file_exists('albums', 'old.jpg'))
        self.assertEqual(await Album.objects.acount(), 0)

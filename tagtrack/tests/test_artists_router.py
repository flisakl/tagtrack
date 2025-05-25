from ninja.testing import TestAsyncClient
from .helper import TestHelper

from tagtrack.routers import artists_router
from tagtrack.models import Artist


class TestArtistRouter(TestHelper):
    def setUp(self):
        self.client = TestAsyncClient(artists_router)

    async def test_artist_can_be_created(self):
        data = {'name': 'Johnny Cash'}
        files = {'image': self.temp_file()}

        response = await self.client.post('', data, FILES=files)
        expected = {
            'id': 1, 'name': 'Johnny Cash', 'image': '/artists/image.jpg',
            'song_count': None, 'album_count': None
        }

        self.assertEqual(response.status_code, 201)
        self.assertJSONEqual(response.content, expected)

    async def test_can_not_create_2_artists_with_the_same_name(self):
        art = await self.create_artist()
        data = {'name': art.name}
        files = {'image': self.temp_file()}

        response = await self.client.post('', data, FILES=files)
        json = response.json()

        self.assertEqual(response.status_code, 422)
        self.assertIn('name', json['detail'][0]['loc'])

    async def test_artists_can_be_filtered(self):
        await self.create_songs()
        params = [
            {'name': 'pearl'},
            {'album_count': 3}
        ]

        res = [await self.client.get('', query_params=x) for x in params]
        json = [r.json() for r in res]

        expected_first = {
            'count': 1,
            'items': [
                {
                    'id': 3,
                    'name': 'Pearl Jam',
                    'song_count': 1,
                    'album_count': 2
                }
            ]
        }
        expected_second = {
            'count': 1,
            'items': [
                {
                    'id': 4,
                    'name': 'Ghost',
                    'song_count': 2,
                    'album_count': 3
                }
            ]
        }
        self.assertTrue(all([r.status_code == 200 for r in res]))
        self.assertJSONMatchesDict(json[0], expected_first)
        self.assertJSONMatchesDict(json[1], expected_second)

    async def test_artist_can_be_fetched(self):
        await self.create_songs()

        res = await self.client.get("/4")
        json = res.json()

        expected = {
            'name': 'Ghost', 'album_count': 3, 'song_count': 2,
            'albums': [
                {'id': 6, 'name': 'Impera', 'genre': 'Pop rock', 'year': 2022},
                {'id': 7, 'name': 'Meliora', 'genre': 'Pop rock', 'year': 2015},
                {'id': 8, 'name': 'Opus Eponymous', 'genre': 'Pop rock', 'year': 2010},
            ]
        }
        self.assertEqual(res.status_code, 200)
        self.assertJSONMatchesDict(json, expected)

    async def test_artist_songs_can_be_fetched(self):
        await self.create_songs()

        res = await self.client.get("/4/songs")
        json = res.json()

        # JSON should contain:
        # *  total number of songs
        # *  list of songs with artists and albums attached
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['count'], 2)
        items = json['items']
        self.assertEqual(items[0]['name'], 'Spirit')
        self.assertTrue(len(items[0]['artists']), 1)
        self.assertTrue(items[0]['album']['name'], 'Impera')
        self.assertEqual(items[1]['name'], 'He Is')
        self.assertTrue(len(items[1]['artists']), 1)
        self.assertTrue(items[1]['album']['name'], 'Impera')

    async def test_artist_can_be_updated(self):
        f = self.temp_file(upload_filename='old.jpg')
        art = await self.create_artist(image=f)
        data = {'name': 'Ghost'}
        f = {'image': self.temp_file()}

        self.assertTrue(self.file_exists('artists', 'old.jpg'))
        res = await self.client.patch(f"/{art.pk}", data, FILES=f)
        json = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['name'], data['name'])
        self.assertFalse(self.file_exists('artists', 'old.jpg'))
        self.assertTrue(self.file_exists('artists', 'image.jpg'))

    async def test_can_not_change_artist_name_to_already_taken_one(self):
        a1 = await self.create_artist('Billy Joel')
        a2 = await self.create_artist('Johnny Cash')
        data = {'name': a2.name}
        files = {'image': self.temp_file()}

        response = await self.client.patch(f'/{a1.pk}', data, FILES=files)
        json = response.json()

        self.assertEqual(response.status_code, 422)
        self.assertIn('name', json['detail'][0]['loc'])

    async def test_artist_can_be_deleted(self):
        f = self.temp_file(upload_filename='old.jpg')
        obj = await self.create_artist('Billy Joel', image=f)

        self.assertTrue(self.file_exists('artists', 'old.jpg'))
        res = await self.client.delete(f"/{obj.pk}")

        self.assertEqual(res.status_code, 204)
        self.assertFalse(self.file_exists('artists', 'old.jpg'))
        self.assertEqual(await Artist.objects.acount(), 0)

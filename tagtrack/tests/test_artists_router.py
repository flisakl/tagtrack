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

        self.assertTrue(all([r.status_code == 200 for r in res]))
        self.assertEqual(json[0]['count'], 1)
        self.assertEqual(json[0]['items'][0]['name'], 'Pearl Jam')
        self.assertEqual(json[1]['count'], 1)
        self.assertEqual(json[1]['items'][0]['name'], 'Ghost')

    async def test_artist_can_be_fetched(self):
        await self.create_songs()

        res = await self.client.get("/4")
        json = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(json['name'], "Ghost")
        self.assertEqual(len(json['albums']), 3)
        self.assertEqual(json['albums'][0]['name'], "Impera")
        self.assertEqual(json['albums'][1]['name'], "Meliora")
        self.assertEqual(json['albums'][2]['name'], "Opus Eponymous")
        self.assertEqual(len(json['songs']), 2)
        self.assertEqual(json['songs'][0]['name'], "Spirit")
        self.assertEqual(json['songs'][1]['name'], "He Is")

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

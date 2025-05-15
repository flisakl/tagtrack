from ninja.testing import TestAsyncClient

from tagtrack.routers import artists_router, albums_router
from tagtrack.models import Artist, Album
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

    async def test_artist_can_be_deleted(self):
        f = self.temp_file(upload_filename='old.jpg')
        obj = await Artist.objects.acreate(name='Romsetin', image=f)
        self.assertTrue(self.file_exists('artists', 'old.jpg'))

        res = await self.client.delete(f"/{obj.pk}")

        self.assertEqual(res.status_code, 204)
        self.assertFalse(self.file_exists('artists', 'old.jpg'))
        self.assertEqual(await Artist.objects.acount(), 0)

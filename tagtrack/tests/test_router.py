from ninja.testing import TestAsyncClient
from .helper import TestHelper

from tagtrack.routers import router


class TestGenericRouter(TestHelper):
    def setUp(self):
        self.client = TestAsyncClient(router)

    async def test_generic_search_endpoint(self):
        await self.create_songs()

        res = await self.client.get('/search', query_params={'name': 'piano'})
        json = res.json()

        artist = {'id': 1, 'name': 'Billy Joel'}
        expected_album = {
            'id': 2,
            'name': 'Piano Man',
            'genre': 'Soft Rock',
            'year': 1973,
            'artist': artist,
        }
        a2 = expected_album.copy()
        del a2['artist']
        expected_song = {
            'id': 4,
            'name': 'Piano Man',
            'year': 1973,
            'genre': 'Soft Rock',
            'duration': 250,
            'number': 1,
            'file': '/songs/song_3.mp3',
            'album': a2,
            'artists': [artist]
        }
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(json['albums']), 1)
        self.assertEqual(len(json['songs']), 1)
        self.assertEqual(len(json['artists']), 0)
        self.assertJSONMatchesDict(json['albums'][0], expected_album)
        self.assertJSONMatchesDict(json['songs'][0], expected_song)

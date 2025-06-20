from ninja.testing import TestAsyncClient
from .helper import TestHelper
from asgiref.sync import sync_to_async
from django.utils.datastructures import MultiValueDict
from django.http import QueryDict
from mutagen import File
import zipfile
from io import BytesIO

from tagtrack.routers import songs_router
from tagtrack.models import Artist, Album, Song
from tagtrack.tags import write_metadata


class TestSongRouter(TestHelper):
    def setUp(self):
        self.client = TestAsyncClient(songs_router)

    async def test_song_can_be_added(self):
        artist = await self.create_artist(name='Squire Tuck')
        a2 = await self.create_artist(name='Octopus')
        album = await self.create_album(
            name='Squire Tuck Soundtracks for the Soul', artist=artist)
        data = QueryDict(mutable=True)
        data.update({
            'name': 'Yearning For Better Days',
            'duration': 166, 'genre': 'Instrumental', 'year': 2018,
            'number': 6, 'album_id': album.pk,
        })
        for x in [artist.pk, a2.pk]:
            data.appendlist('artist_ids', x)
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

    async def test_song_can_not_be_added_without_audio_file(self):
        artist = await self.create_artist(name='Squire Tuck')
        a2 = await self.create_artist(name='Octopus')
        album = await self.create_album(
            name='Squire Tuck Soundtracks for the Soul', artist=artist)
        data = QueryDict(mutable=True)
        data.update({
            'name': 'Yearning For Better Days',
            'duration': 166, 'genre': 'Instrumental', 'year': 2018,
            'number': 6, 'album_id': album.pk,
        })
        for x in [artist.pk, a2.pk]:
            data.appendlist('artist_ids', x)
        files = {
            'image': self.temp_file(),
        }

        response = await self.client.post('', data=data, FILES=files)
        json = response.json()

        self.assertEqual(response.status_code, 422)
        self.assertIn('file', json['detail'][0]['loc'])

    async def test_songs_can_be_filtered(self):
        albums = await self.create_albums()
        await self.create_songs(albums)
        rdata = [
            {'genre': 'rock'},
            {'name': 'judy'},
            {'year_min': 1970, 'year_max': 1980},
            {'duration_max': 200},
            {'album_id': albums[8].pk},
            {'album_name': 'piano'},
        ]

        r = [await self.client.get('', query_params=rd) for rd in rdata]
        j = [x.json() for x in r]

        expected = {
            'count': 1,
            'items': [{
                'id': 4,
                'file': '/songs/song_3.mp3',
                'number': 1,
                'name': 'Piano Man',
                'genre': 'Soft Rock',
                'duration': 250,
                'year': 1973,
                'artists': [
                    {'id': 1, 'name': 'Billy Joel'}
                ],
                'album': {
                    'id': 2,
                    'name': 'Piano Man',
                    'year': 1973,
                    'genre': 'Soft Rock',
                }
            }]
        }

        self.assertTrue(all([x.status_code == 200 for x in r]))
        self.assertEqual(j[0]['count'], 5)
        self.assertEqual(j[1]['count'], 1)
        self.assertEqual(j[2]['count'], 2)
        self.assertEqual(j[3]['count'], 3)
        self.assertJSONMatchesDict(j[5], expected)

    async def test_song_can_be_fetched(self):
        f = self.temp_file('song.mp3', 'audio/mpeg', 'song_0.mp3')
        art = await self.create_artist(name='Rammstein')
        alb = await self.create_album(name='Rosenrot', artist=art)
        obj = await self.create_song(f, album=alb, artists=[art])

        res = await self.client.get(f"/{obj.pk}")
        json = res.json()

        expected = {
            'id': obj.pk,
            'file': '/songs/song_0.mp3',
            'number': obj.number,
            'name': obj.name,
            'genre': obj.genre,
            'duration': obj.duration,
            'year': obj.year,
            'artists': [
                {'id': art.pk, 'name': art.name}
            ],
            'album': {
                'id': alb.pk,
                'name': alb.name,
                'year': alb.year,
                'genre': alb.genre,
            }
        }
        self.assertEqual(res.status_code, 200)
        self.assertJSONMatchesDict(json, expected)

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
        data = QueryDict(mutable=True)
        data.update({'name': 'New name', 'duration': 145, 'album_id': 5})
        for x in [artist.pk]:
            data.appendlist('artist_ids', x)

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

    async def test_songs_can_be_uploaded(self):
        meta = [
            {
                'name': 'Lose Yourself',
                'genre': 'Rap',
                'year': 2012,
                'number': 4,
                'artists': [{'name': 'Eminem'}, {'name': 'Rihanna'}],
                'album': {'name': 'The Marshall', 'artist': 'Eminem'}
            },
            {
                'name': 'Rap God',
                'genre': 'Rap',
                'year': 2013,
                'number': 4,
                'artists': [{'name': 'Eminem'}],
                'album': {'name': 'The Marshall', 'artist': 'Eminem'}
            },
            {
                'name': '',
                'genre': 'Rock',
                'year': 1996,
                'number': 2,
                'artists': [{'name': 'Pearl Jam'}],
                'album': {'name': 'No Code'}
            },
            {
                'name': 'Battery',
                'genre': 'Metal',
                'year': 1986,
                'number': 1,
                'artists': [{'name': 'Metallica'}],
                'album': {'name': 'Master of Puppets'}
            },
            {
                'name': 'If You Have Ghosts',
                'genre': 'Pop',
                'year': 2013,
                'number': 1,
                'artists': [{'name': 'Ghost'}],
                'album': {'name': 'If You Have Ghost'}
            },
        ]

        f = [
            self.temp_file('song.mp3', 'audio/mpeg', "song_0_special.mp3"),
            self.temp_file('song.flac', 'audio/flac', "song_0_special.flac"),
            self.temp_file('song.opus', 'audio/ogg', "song_0_special.opus"),
            self.temp_file('song.ogg', 'audio/ogg', "song_0_special.ogg"),
            self.temp_file('song.mp4', 'audio/mp4', "song_0_special.mp4"),
        ]

        for i, data in enumerate(meta):
            write_metadata(f[i], data)

        f = MultiValueDict({'files': f})

        response = await self.client.post('/upload', FILES=f)
        json = response.json()

        expected = {
            'total_count':  5,
            'invalid_count':  0,
            'invalid_files':  [],
        }
        self.assertEqual(response.status_code, 200)
        self.assertJSONMatchesDict(json, expected)
        # Check if artists are created
        artists = await sync_to_async(list)(Artist.objects.all())
        self.assertEqual(len(artists), 5)
        for art in artists:
            self.assertIn(art.name, ['Pearl Jam', 'Eminem', 'Rihanna', 'Ghost',
                                     'Metallica', 'Billy Joel'])
        # Check if albums are created and artists are attached
        albums = await sync_to_async(list)(Album.objects.select_related('artist').all())
        self.assertEqual(len(albums), 4)
        for alb in albums:
            if alb.name == meta[0]['album']['name']:
                self.assertEqual(alb.artist.name, meta[0]['album']['artist'])
                self.assertEqual(alb.year, meta[0]['year'])
                # Despite setting album genre to 'Hip-Hop', Rap is picked
                # because it is most occurring genre in songs from this album
                self.assertEqual(alb.genre, 'Rap')
            if alb.name == meta[2]['album']['name']:
                self.assertEqual(alb.artist.name, 'Pearl Jam')
                self.assertEqual(alb.year, meta[2]['year'])
                self.assertEqual(alb.genre, 'Rock')
            if alb.name == meta[3]['album']['name']:
                self.assertEqual(alb.artist.name, 'Metallica')
                self.assertEqual(alb.year, meta[3]['year'])
                self.assertEqual(alb.genre, 'Metal')
            if alb.name == meta[4]['album']['name']:
                self.assertEqual(alb.artist.name, 'Ghost')
                self.assertEqual(alb.year, meta[4]['year'])
                self.assertEqual(alb.genre, 'Pop')
        # Check if songs are created
        qs = Song.objects.prefetch_related('artists').select_related('album').all()
        songs = await sync_to_async(list)(qs)
        self.assertEqual(len(songs), 5)
        first = songs[0]
        second = songs[1]
        third = songs[2]
        fourth = songs[3]
        fifth = songs[4]
        self.assertEqual(len(first.artists.all()), 2)
        self.assertEqual(first.album.name, meta[0]['album']['name'])
        self.assertEqual(len(second.artists.all()), 1)
        self.assertEqual(second.album.name, meta[0]['album']['name'])
        self.assertEqual(len(third.artists.all()), 1)
        self.assertEqual(third.album.name, meta[2]['album']['name'])
        self.assertEqual(len(fourth.artists.all()), 1)
        self.assertEqual(fourth.album.name, meta[3]['album']['name'])
        self.assertEqual(len(fifth.artists.all()), 1)
        self.assertEqual(fifth.album.name, meta[4]['album']['name'])

    async def test_untagged_files_can_be_uploaded(self):
        files = [
            self.temp_file('song.mp3', 'audio/mpeg', f"song_untagged{x}.mp3")
            for x in range(3)
        ]
        for f in files:
            file = File(f.temporary_file_path())
            file.delete()
        f = MultiValueDict({'files': files})

        response = await self.client.post('/upload', FILES=f)
        json = response.json()

        expected = {
            'total_count':  3,
            'invalid_count':  0,
            'invalid_files':  [],
        }
        self.assertEqual(response.status_code, 200)
        self.assertJSONMatchesDict(json, expected)
        self.assertEqual(3, await Song.objects.acount())
        self.assertEqual(0, await Album.objects.acount())
        self.assertEqual(0, await Artist.objects.acount())

    async def test_junk_files_are_ignored(self):
        files = [
            self.temp_file('song.mp3', 'audio/mpeg', "song_untagged_0.mp3"),
            self.temp_file('junk.mp3', 'audio/mpeg', "junk_untagged_1.mp3"),
            self.temp_file('junk.jpg', 'audio/mpeg', "junk_untagged_1.jpg"),
        ]
        File(files[0].temporary_file_path()).delete()
        f = MultiValueDict({'files': files})

        response = await self.client.post('/upload', FILES=f)
        json = response.json()

        expected = {
            'total_count':  3,
            'invalid_count':  2,
            'invalid_files':  [
                "junk_untagged_1.mp3",
                "junk_untagged_1.jpg",
            ],
        }
        self.assertEqual(response.status_code, 200)
        self.assertJSONMatchesDict(json, expected)
        self.assertEqual(1, await Song.objects.acount())
        self.assertEqual(0, await Album.objects.acount())
        self.assertEqual(0, await Artist.objects.acount())

    async def test_songs_can_be_downloaded(self):
        s1 = await self.create_song(
            self.temp_file('song.mp3', 'audio/mpeg', 'song1.mp3')
        )
        s2 = await self.create_song(
            self.temp_file('song.mp3', 'audio/mpeg', 'song2.mp3')
        )

        response = await self.client.get('/download', query_params={'song_ids': [s1.pk, s2.pk]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/zip')
        self.assertTrue(response.headers['Content-Disposition'].startswith('attachment'))
        zip_content = BytesIO(response.content)
        with zipfile.ZipFile(zip_content) as zf:
            names = zf.namelist()
        self.assertIn('song1.mp3', names)
        self.assertIn('song2.mp3', names)

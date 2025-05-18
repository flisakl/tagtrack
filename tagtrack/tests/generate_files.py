import subprocess
from pathlib import Path
from PIL import Image
import numpy as np
import wave
from mutagen.id3 import ID3, TIT2, TALB, TDRC, TCON, TRCK, APIC, TPE1
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4, MP4Cover

# === Configuration ===
output_dir = Path("test_files")
output_dir.mkdir(exist_ok=True)
image_path = output_dir / "image.jpg"
wav_path = output_dir / "song.wav"
audio_formats = ["mp3", "flac", "opus", "ogg"]

metadata = {
    "title": "Why Judy Why",
    "album": {
        "name": "Cold Spring Harbor",
        "release_year": "1970",
        "genre": "Electronic",
        "cover_image": str(image_path)
    },
    "position": "1",
    "artists": [
        {"name": "Billy Joel", "image": str(image_path)},
        {"name": "Kaneko Ayano", "image": str(image_path)}
    ]
}

# === Generate a solid color JPG ===


def generate_image(path):
    img = Image.new("RGB", (500, 500), (123, 104, 238))  # Medium Slate Blue
    img.save(path, "JPEG")

# === Generate a 1-second WAV file (sine wave) ===


def generate_wav(path):
    framerate = 44100
    duration = 1  # seconds
    frequency = 440  # Hz

    t = np.linspace(0, duration, int(framerate * duration), endpoint=False)
    data = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)

    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(framerate)
        wav_file.writeframes(data.tobytes())

# === Convert WAV to other formats ===


def convert_audio(wav_path: Path, format: str, output_dir: Path) -> Path:
    output_file = output_dir / f"{wav_path.stem}.{format}"

    codec_map = {
        "mp3": "libmp3lame",
        "flac": "flac",
        "opus": "libopus",
        "ogg": "libvorbis",  # 🔥 THIS IS IMPORTANT
    }

    codec = codec_map.get(format)
    if codec is None:
        raise ValueError(f"Unsupported format: {format}")

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite
        "-i", str(wav_path),
        "-c:a", codec,
        str(output_file)
    ]

    subprocess.run(cmd, check=True)
    return output_file

# === Embed metadata and cover ===


def embed_metadata(filepath, format, metadata):
    album = metadata["album"]
    artists = metadata["artists"]  # list of artist dicts
    title = metadata["title"]
    year = album["release_year"]
    genre = album["genre"]
    track = metadata["position"]
    album_name = album["name"]
    cover_path = album["cover_image"]

    # Load album cover image
    cover_data = open(cover_path, "rb").read()
    artist_names = [artist["name"] for artist in artists]

    if format == "mp3":
        audio = ID3()
        audio.add(TIT2(encoding=3, text=title))
        audio.add(TALB(encoding=3, text=album_name))
        audio.add(TDRC(encoding=3, text=year))
        audio.add(TCON(encoding=3, text=genre))
        audio.add(TRCK(encoding=3, text=track))
        audio.add(TPE1(encoding=3, text=artist_names))

        # Add album cover
        audio.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_data))

        # Add artist pictures
        for artist in artists:
            img_data = open(artist["image"], "rb").read()
            audio.add(APIC(
                encoding=3,
                mime="image/jpeg",
                type=8,
                desc=artist["name"],  # Use artist name as description
                data=img_data
            ))

        audio.save(filepath)

    elif format == "flac":
        audio = FLAC(filepath)
        audio["title"] = title
        audio["album"] = album_name
        audio["date"] = year
        audio["genre"] = genre
        audio["tracknumber"] = track
        audio["artist"] = artist_names

        # Add album cover
        pic = Picture()
        pic.data = cover_data
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.width = 500
        pic.height = 500
        pic.depth = 24
        audio.add_picture(pic)

        # Add artist pictures
        for artist in artists:
            img_data = open(artist["image"], "rb").read()
            pic = Picture()
            pic.data = img_data
            pic.type = 8  # Other
            pic.mime = "image/jpeg"
            pic.width = 500
            pic.height = 500
            pic.depth = 24
            pic.description = artist["name"]
            audio.add_picture(pic)

        audio.save()

    elif format in ["ogg", "opus"]:
        if fmt == "ogg":
            audio = OggVorbis(filepath)
        elif fmt == "opus":
            audio = OggOpus(filepath)
        audio["title"] = title
        audio["album"] = album_name
        audio["date"] = year
        audio["genre"] = genre
        audio["tracknumber"] = track
        audio["artist"] = artist_names
        audio.save()
        # OggVorbis does not support embedded images via Mutagen

    elif format == "m4a":
        audio = MP4(filepath)
        audio["\xa9nam"] = title
        audio["\xa9alb"] = album_name
        audio["\xa9day"] = year
        audio["\xa9gen"] = genre
        audio["trkn"] = [(int(track), 0)]
        audio["\xa9ART"] = artist_names

        # Embed album cover only (MP4 supports only one cover image)
        audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
        audio.save()


# Generate junk files
def generate_junk_file(fname: str):
    fp = f"./{output_dir.joinpath(fname)}"
    f = open(str(fp), "wb")
    f.write(b"")
    f.close()


# === Run All Tasks ===
generate_image(image_path)
generate_wav(wav_path)

for fmt in audio_formats:
    output_path = convert_audio(wav_path, fmt, output_dir)
    embed_metadata(str(output_path), fmt, metadata)

generate_junk_file("junk.mp3")
generate_junk_file("junk.jpg")
print("All audio files created and metadata embedded.")

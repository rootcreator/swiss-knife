import os
import sys
import re
import yt_dlp
import eyed3
from tqdm import tqdm
from dotenv import load_dotenv
import requests
import logging

# Suppress yt-dlp debug messages
logging.getLogger('yt_dlp').setLevel(logging.ERROR)

# Load .env file
load_dotenv()
DEFAULT_OUTPUT_FOLDER = os.getenv("DEFAULT_OUTPUT_FOLDER", "downloads")
DEFAULT_QUALITY = os.getenv("DEFAULT_QUALITY", "medium")
DEFAULT_FORMAT = os.getenv("DEFAULT_FORMAT", "mp3")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))

def sanitize_filename(name):
    """Removes invalid filename characters."""
    if not name:
        return "Unknown"
    return "".join(c for c in name if c.isalnum() or c in " .-_").rstrip()

def validate_youtube_url(url):
    """Validate YouTube URL (both video and playlist)."""
    patterns = [
        r'^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/',
        r'^(https?://)?(www\.)?(music\.youtube\.com)/'
    ]
    return any(re.match(pattern, url) for pattern in patterns)

def is_playlist_url(url):
    """Check if URL is a playlist."""
    playlist_patterns = [
        r'list=',
        r'/playlist/'
    ]
    return any(pattern in url for pattern in playlist_patterns)

def download_thumbnail(url):
    """Download image bytes from URL for tagging."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        tqdm.write(f"⚠️ Failed to download thumbnail: {e}")
        return None

def get_file_size_mb(file_path):
    """Get file size in MB."""
    try:
        return os.path.getsize(file_path) / (1024 * 1024)
    except:
        return 0

def find_downloaded_file(output_folder, title, index=None, file_format="mp3"):
    """Find downloaded file when the actual filename differs from expected."""
    if index is not None:
        expected_name = f"{index:02d} - {sanitize_filename(title)}.{file_format}"
    else:
        expected_name = f"{sanitize_filename(title)}.{file_format}"
    
    expected_path = os.path.join(output_folder, expected_name)
    
    if os.path.exists(expected_path):
        return expected_path
    
    # Search for files containing part of the title
    title_part = sanitize_filename(title)[:20]
    for filename in os.listdir(output_folder):
        if filename.endswith(f'.{file_format}'):
            if title_part in sanitize_filename(filename):
                return os.path.join(output_folder, filename)
    
    return None

def tag_mp3(file_path, title=None, artist=None, album=None, track_num=None, total_tracks=None, image_bytes=None):
    """Add metadata tags and cover art to MP3 files."""
    try:
        if not os.path.exists(file_path):
            tqdm.write(f"⚠️ File not found for tagging: {file_path}")
            return False
        
        audiofile = eyed3.load(file_path)
        
        if audiofile is None:
            tqdm.write(f"⚠️ Could not load MP3: {file_path}")
            return False
            
        if audiofile.tag is None:
            audiofile.initTag(version=(2, 3, 0))
            
        if title: 
            audiofile.tag.title = title
        if artist: 
            audiofile.tag.artist = artist
        if album: 
            audiofile.tag.album = album
        if track_num and total_tracks: 
            audiofile.tag.track_num = (track_num, total_tracks)
        if image_bytes: 
            audiofile.tag.images.set(3, image_bytes, "image/jpeg", u"Cover")
            
        audiofile.tag.save()
        return True
        
    except Exception as e:
        tqdm.write(f"⚠️ Could not tag {file_path}: {e}")
        return False

def get_ydl_opts(output_folder, preferred_quality, hook, is_playlist=False, file_format="mp3"):
    """Get yt-dlp configuration options."""
    if is_playlist:
        outtmpl = f"{output_folder}/%(title)s.%(ext)s"
    else:
        outtmpl = f"{output_folder}/%(title)s.%(ext)s"
    
    # Common options
    ydl_opts = {
        "outtmpl": outtmpl,
        "writethumbnail": True,
        "noplaylist": not is_playlist,
        "quiet": True,
        "ignoreerrors": True,
        "continuedl": True,
        "retries": MAX_RETRIES,
        "socket_timeout": REQUEST_TIMEOUT,
        "progress_hooks": [hook],
        "suppress_warnings": ["SABR"],
    }
    
    # MP3 specific options
    if file_format == "mp3":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": preferred_quality,
                },
                {
                    'key': 'FFmpegMetadata',
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                },
            ],
        })
    # MP4 specific options
    elif file_format == "mp4":
        quality_map = {
            "low": "best[height<=480]",
            "medium": "best[height<=720]",
            "high": "best[height<=1080]"
        }
        video_quality = quality_map.get(preferred_quality, "best[height<=720]")
        
        ydl_opts.update({
            "format": f"{video_quality}/best",
            "merge_output_format": "mp4",
            "postprocessors": [
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                },
                {
                    'key': 'FFmpegMetadata',
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                },
            ],
        })
    
    return ydl_opts

def download_single_video(video_url, output_folder=None, quality="medium", file_format="mp3"):
    """Download a single YouTube video as MP3 or MP4."""
    if not validate_youtube_url(video_url):
        print("❌ Invalid YouTube URL")
        return
    
    quality_map_audio = {"low": "128", "medium": "192", "high": "320"}
    quality_map_video = {"low": "480p", "medium": "720p", "high": "1080p"}
    
    if file_format == "mp3":
        preferred_quality = quality_map_audio.get(quality, "192")
        quality_display = f"{preferred_quality} kbps"
    else:
        preferred_quality = quality
        quality_display = quality_map_video.get(quality, "720p")
    
    print(f"🎵 Downloading single video as {file_format.upper()}")
    print(f"🎚️ Quality: {quality_display}\n")

    # Get video metadata
    metadata_opts = {
        "quiet": True,
        "ignoreerrors": True
    }
    
    with yt_dlp.YoutubeDL(metadata_opts) as meta_ydl:
        try:
            info = meta_ydl.extract_info(video_url, download=False)
        except Exception as e:
            print(f"❌ Failed to load video: {e}")
            return

    if not info:
        print("❌ Invalid video or video not found.")
        return
        
    video_title = sanitize_filename(info.get("title", "Unknown Title"))
    artist = info.get("uploader", "Unknown Artist")
    thumb_url = info.get("thumbnail")
    
    print(f"🎬 Video: {video_title}")
    print(f"👤 Artist: {artist}\n")

    # Folder setup
    if not output_folder or output_folder == DEFAULT_OUTPUT_FOLDER:
        if file_format == "mp3":
            output_folder = os.path.join(DEFAULT_OUTPUT_FOLDER, "Single Tracks")
        else:
            output_folder = os.path.join(DEFAULT_OUTPUT_FOLDER, "Videos")
    
    output_folder = os.path.normpath(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    # Download thumbnail (for MP3 tagging)
    album_art = download_thumbnail(thumb_url) if thumb_url and file_format == "mp3" else None

    # Setup progress bar
    progress_bar = tqdm(total=1, unit="file", position=0, leave=True)

    def hook(d):
        if d["status"] == "downloading":
            filename = os.path.basename(d.get('filename', ''))
            progress_bar.set_description(f"⬇️ {filename[:40]}...")
        elif d["status"] == "finished":
            file_size = get_file_size_mb(d.get('filename', ''))
            tqdm.write(f"✅ Finished: {os.path.basename(d.get('filename', ''))} ({file_size:.1f} MB)")

    # Download
    ydl_opts = get_ydl_opts(output_folder, preferred_quality, hook, is_playlist=False, file_format=file_format)
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # Tag MP3 files
        if file_format == "mp3":
            mp3_path = find_downloaded_file(output_folder, video_title, file_format="mp3")
            if mp3_path and os.path.exists(mp3_path):
                tag_success = tag_mp3(
                    mp3_path,
                    title=video_title,
                    artist=artist,
                    album="Single Track",
                    image_bytes=album_art,
                )
                if tag_success:
                    tqdm.write(f"🏷️  Tagged: {os.path.basename(mp3_path)}")
            else:
                tqdm.write(f"⚠️ Could not find MP3 file for tagging: {video_title}")
        else:
            # For MP4, just confirm download
            mp4_path = find_downloaded_file(output_folder, video_title, file_format="mp4")
            if mp4_path:
                tqdm.write(f"🎬 MP4 ready: {os.path.basename(mp4_path)}")
            
    except Exception as e:
        tqdm.write(f"❌ Error downloading {video_title}: {e}")
    
    progress_bar.close()
    print(f"\n🎉 Download completed!")
    print(f"📁 Location: {output_folder}")
    print(f"✅ '{video_title}' downloaded as {file_format.upper()}!\n")

def download_playlist(playlist_url, output_folder=None, quality="medium", file_format="mp3"):
    """Downloads all videos in a YouTube playlist as MP3 or MP4."""
    
    if not validate_youtube_url(playlist_url):
        print("❌ Invalid YouTube URL")
        return
    
    quality_map_audio = {"low": "128", "medium": "192", "high": "320"}
    quality_map_video = {"low": "480p", "medium": "720p", "high": "1080p"}
    
    if file_format == "mp3":
        preferred_quality = quality_map_audio.get(quality, "192")
        quality_display = f"{preferred_quality} kbps"
    else:
        preferred_quality = quality
        quality_display = quality_map_video.get(quality, "720p")
    
    print(f"🎧 Downloading playlist as {file_format.upper()}")
    print(f"🎚️ Quality: {quality_display}\n")

    # Get playlist metadata
    metadata_opts = {
        "quiet": True, 
        "extract_flat": True,
        "ignoreerrors": True
    }
    
    with yt_dlp.YoutubeDL(metadata_opts) as meta_ydl:
        try:
            info = meta_ydl.extract_info(playlist_url, download=False)
        except Exception as e:
            print(f"❌ Failed to load playlist: {e}")
            return

    if not info or "entries" not in info:
        print("❌ Invalid or empty playlist.")
        return
        
    playlist_title = sanitize_filename(info.get("title", "Unknown Album"))
    total_tracks = len(info.get("entries", []))
    
    content_type = "Album" if file_format == "mp3" else "Playlist"
    print(f"📀 {content_type}: {playlist_title}")
    print(f"📦 Total videos: {total_tracks}\n")

    # Folder setup
    if not output_folder or output_folder == DEFAULT_OUTPUT_FOLDER:
        output_folder = os.path.join(DEFAULT_OUTPUT_FOLDER, playlist_title)
    
    output_folder = os.path.normpath(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    # Download album cover (for MP3 tagging)
    thumb_url = info.get("thumbnail")
    global_album_art = download_thumbnail(thumb_url) if thumb_url and file_format == "mp3" else None

    # Setup progress bar
    progress_bar = tqdm(total=total_tracks, unit="file", position=0, leave=True)
    downloaded_count = 0
    skipped_count = 0
    error_count = 0

    def hook(d):
        nonlocal downloaded_count
        if d["status"] == "downloading":
            filename = os.path.basename(d.get('filename', ''))
            progress_bar.set_description(f"⬇️ {filename[:40]}...")
        elif d["status"] == "finished":
            downloaded_count += 1
            file_size = get_file_size_mb(d.get('filename', ''))
            tqdm.write(f"✅ Finished: {os.path.basename(d.get('filename', ''))} ({file_size:.1f} MB)")

    # Download + Tag
    ydl_opts = get_ydl_opts(output_folder, preferred_quality, hook, is_playlist=True, file_format=file_format)
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for entry in info["entries"]:
            if not entry or not entry.get("title"):
                tqdm.write("⚠️ Skipping invalid or deleted entry")
                error_count += 1
                progress_bar.update(1)
                continue

            title = entry.get("title", "Unknown Title")
            artist = entry.get("uploader", "Unknown Artist")
            index = entry.get("playlist_index", 0)
            
            # Check if file already exists
            expected_filename = f"{index:02d} - {sanitize_filename(title)}.{file_format}"
            expected_path = os.path.join(output_folder, expected_filename)
            
            if os.path.exists(expected_path):
                tqdm.write(f"⏩ Skipping (already exists): {expected_filename}")
                skipped_count += 1
                progress_bar.update(1)
                continue

            try:
                ydl.download([entry["url"]])
                
                # Tag MP3 files after download
                if file_format == "mp3":
                    mp3_path = find_downloaded_file(output_folder, title, index, "mp3")
                    if mp3_path and os.path.exists(mp3_path):
                        tag_success = tag_mp3(
                            mp3_path,
                            title=title,
                            artist=artist,
                            album=playlist_title,
                            track_num=index,
                            total_tracks=total_tracks,
                            image_bytes=global_album_art,
                        )
                        if tag_success:
                            tqdm.write(f"🏷️  Tagged: {os.path.basename(mp3_path)}")
                    else:
                        tqdm.write(f"⚠️ Could not find MP3 file for tagging: {title}")
                else:
                    # For MP4, just confirm
                    mp4_path = find_downloaded_file(output_folder, title, index, "mp4")
                    if mp4_path:
                        tqdm.write(f"🎬 MP4 ready: {os.path.basename(mp4_path)}")
                    
            except Exception as e:
                tqdm.write(f"❌ Error downloading {title}: {e}")
                error_count += 1
                continue

    progress_bar.close()
    
    # Final summary
    print(f"\n🎉 Download completed!")
    print(f"📁 Location: {output_folder}")
    print(f"📊 Summary: {downloaded_count} downloaded, {skipped_count} skipped, {error_count} errors")
    print(f"✅ All {file_format.upper()} files from '{playlist_title}' processed!\n")

def main():
    """Main function that handles both single videos and playlists."""
    if len(sys.argv) < 2:
        print("\n🎵 YouTube Downloader - MP3 & MP4")
        print("=" * 45)
        print("\nUsage:")
        print("  python music.py <youtube_url> [format] [quality] [output_folder]")
        print("\nArguments (all optional, order matters):")
        print("  format: mp3 (audio) or mp4 (video)")
        print("  quality: low, medium, high")
        print("  output_folder: custom output directory")
        print("\nExamples:")
        print("  Single Video - MP3:")
        print("    python music.py 'https://youtu.be/VIDEO_ID'")
        print("    python music.py 'https://youtube.com/watch?v=VIDEO_ID' mp3 high")
        print("  Single Video - MP4:")
        print("    python music.py 'https://youtu.be/VIDEO_ID' mp4")
        print("    python music.py 'https://youtube.com/watch?v=VIDEO_ID' mp4 high MyVideos")
        print("  Playlist - MP3:")
        print("    python music.py 'https://youtube.com/playlist?list=PLAYLIST_ID'")
        print("    python music.py 'https://youtube.com/playlist?list=PLAYLIST_ID' mp3 medium MyAlbum")
        print("  Playlist - MP4:")
        print("    python music.py 'https://youtube.com/playlist?list=PLAYLIST_ID' mp4")
        print("    python music.py 'https://youtube.com/playlist?list=PLAYLIST_ID' mp4 high MyPlaylist")
        print("\nDefault values:")
        print(f"  Format: {DEFAULT_FORMAT}")
        print(f"  Quality: {DEFAULT_QUALITY}")
        print(f"  Output: {DEFAULT_OUTPUT_FOLDER}\n")
        sys.exit(1)

    youtube_url = sys.argv[1]
    
    # Parse optional arguments
    file_format = DEFAULT_FORMAT
    quality = DEFAULT_QUALITY
    output_folder = DEFAULT_OUTPUT_FOLDER
    
    # Check for format in arguments
    for i in range(2, min(5, len(sys.argv))):
        arg = sys.argv[i].lower()
        if arg in ["mp3", "mp4"]:
            file_format = arg
        elif arg in ["low", "medium", "high"]:
            quality = arg
        else:
            # Assume it's an output folder if not a recognized option
            output_folder = sys.argv[i]
    
    # Validate parameters
    if file_format not in ["mp3", "mp4"]:
        print(f"⚠️ Invalid format '{file_format}'. Using default: {DEFAULT_FORMAT}")
        file_format = DEFAULT_FORMAT
    
    if quality not in ["low", "medium", "high"]:
        print(f"⚠️ Invalid quality '{quality}'. Using default: {DEFAULT_QUALITY}")
        quality = DEFAULT_QUALITY

    # Validate YouTube URL
    if not validate_youtube_url(youtube_url):
        print("❌ Error: Please provide a valid YouTube URL")
        sys.exit(1)

    content_type = "MP3 Audio" if file_format == "mp3" else "MP4 Video"
    print(f"🎵 Processing: {youtube_url}")
    print(f"📦 Format: {content_type}")
    print(f"💾 Saving to: {output_folder}")
    print(f"⚙️ Quality: {quality}\n")
    
    try:
        if is_playlist_url(youtube_url):
            download_playlist(youtube_url, output_folder, quality, file_format)
        else:
            download_single_video(youtube_url, output_folder, quality, file_format)
    except KeyboardInterrupt:
        print("\n❌ Download interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

"""Generate synthetic audio/video locally; no external media is downloaded."""
from pathlib import Path
import shutil
import subprocess
from bootstrap import main as bootstrap

ROOT = Path(__file__).resolve().parents[1]


def main():
    bootstrap()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("FFmpeg is optional. Add your own MP3/MP4 files, or install FFmpeg to generate demo media.")
    audio = ROOT / "media_files" / "mp3_public" / "演示音频：二十秒测试音.mp3"
    video = ROOT / "media_files" / "mp4_public" / "演示视频：色彩画面.mp4"
    if not audio.exists():
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=20", "-codec:a", "libmp3lame", "-q:a", "7", str(audio)], check=True)
    if not video.exists():
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x2563eb:s=640x360:d=12", "-f", "lavfi", "-i", "sine=frequency=330:duration=12", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", "-shortest", str(video)], check=True)
    print("Synthetic MP3 and MP4 demo files are ready.")


if __name__ == "__main__":
    main()

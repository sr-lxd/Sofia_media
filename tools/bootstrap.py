"""Create private virtual configuration without overwriting existing files."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    for source, target in ((".env.example", ".env"), ("user.dic.example", "user.dic")):
        destination = ROOT / target
        if not destination.exists():
            shutil.copyfile(ROOT / source, destination)
            print(f"Created {target} from virtual example")
    (ROOT / "media_files" / "mp3_public").mkdir(parents=True, exist_ok=True)
    (ROOT / "media_files" / "mp4_public").mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    main()

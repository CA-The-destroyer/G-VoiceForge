"""Package reviewed Git-tracked source only; never sweep the working directory."""
from pathlib import Path
import hashlib
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {"data", "models", "releases", ".venv", "node_modules", "dist", "__pycache__", ".git"}
FORBIDDEN_SUFFIXES = {".wav", ".mp3", ".ogg", ".flac", ".mp4", ".zip", ".db", ".sqlite", ".pyc"}

def source_files():
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    paths = [Path(p.decode("utf-8")) for p in raw.split(b"\0") if p]
    if not paths:
        raise SystemExit("No tracked source files. Review and commit source first.")
    for path in paths:
        if (any(part in FORBIDDEN_PARTS for part in path.parts)
                or path.suffix.lower() in FORBIDDEN_SUFFIXES
                or path.name.startswith(".env") or (ROOT/path).is_symlink()):
            raise SystemExit(f"Refusing non-source path: {path}")
    return sorted(paths)

if __name__ == "__main__":
    paths = source_files()
    output_dir = ROOT/"releases"
    output_dir.mkdir(exist_ok=True)
    archive = output_dir/"G-VoiceForge-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in paths:
            output.write(ROOT/path, path.as_posix())
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
    (output_dir/"SHA256SUMS.txt").write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest()+"  "+archive.name+"\n")
    print(archive)

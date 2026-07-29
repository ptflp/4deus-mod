from pathlib import Path
import shutil
import subprocess
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "native/mangoapp_fdinfo_guard.rs"
OUTPUT = PROJECT_ROOT / "bin/mangoapp-fdinfo-guard.so"


def main():
    command = [
        "rustc",
        "--edition=2021",
        "--crate-type=cdylib",
        "-C",
        "opt-level=z",
        "-C",
        "panic=abort",
        "-C",
        "strip=symbols",
        str(SOURCE),
        "-o",
        str(OUTPUT),
    ]

    if shutil.which("cc"):
        subprocess.run(command, check=True)
        return

    libgcc = Path("/usr/lib/libgcc_s.so.1")
    if not libgcc.is_file():
        raise RuntimeError("A C linker or /usr/lib/libgcc_s.so.1 is required")

    with tempfile.TemporaryDirectory(
        prefix="4deus-native-link-",
    ) as link_directory:
        link_path = Path(link_directory)
        (link_path / "libgcc_s.so").symlink_to(libgcc)
        command[1:1] = [
            "-C",
            "linker=rust-lld",
            "-C",
            f"link-arg=-L{link_path}",
            "-C",
            "link-arg=-L/usr/lib",
        ]
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()

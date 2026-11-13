"""Fill in missing LiteKB Compose credentials in the current directory."""
import os
import re
import secrets
from pathlib import Path


def main():
    path = Path(".env")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "r+b") as env_file:
        # Lock through the read and append so two initializers always agree on the instance keys.
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        original = env_file.read()
        defined = set(re.findall(r"^[ \t]*(?:export[ \t]+)?(\w+)[ \t]*[=:]", original.decode("utf-8-sig"), re.M))
        entries = []
        for name in ("LITEKB_DB_PASSWORD", "LITEKB_REDIS_PASSWORD", "LITEKB_SECRET_KEY", "LITEKB_ADMIN_PASSWORD"):
            if name in defined:
                continue
            # The control panel accepts up to 20 characters and requires all four character types.
            value = secrets.token_urlsafe(12) + "aA1!" if name == "LITEKB_ADMIN_PASSWORD" else secrets.token_urlsafe(32)
            entries.append(f"{name}={value}".encode("ascii"))
        if entries:
            newline = b"\r\n" if b"\r\n" in original else b"\n"
            if original and not original.endswith(b"\n"):
                env_file.write(newline)
            env_file.write(newline.join(entries) + newline)
            env_file.flush()
            os.fsync(fd)
    print(f"{path.resolve()}: added {len(entries)} missing settings")


if __name__ == "__main__":
    main()

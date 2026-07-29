import os
from pathlib import Path
import tempfile
import unittest

from steamos_application import (
    STEAM_ID64_BASE,
    SteamOsApplicationManager,
)


class SteamOsApplicationManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.home = root / "home"
        self.home.mkdir()
        self.launcher = root / "usr/bin/steamos-nested-desktop"
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("#!/bin/sh\n", encoding="utf-8")
        self.assets = root / "assets"
        self.assets.mkdir()
        for name in (
            "capsule.png",
            "hero.png",
            "icon.png",
            "logo.png",
            "store-capsule.png",
        ):
            (self.assets / name).write_bytes(name.encode())
        self.manager = SteamOsApplicationManager(
            home=self.home,
            nested_desktop=self.launcher,
            asset_directory=self.assets,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_prepare_installs_current_executable_wrapper(self):
        self.assertFalse(self.manager.status()["wrapperInstalled"])

        profile = self.manager.prepare()

        self.assertEqual(profile["name"], "Steam Os")
        self.assertIn("Nested Desktop", profile["aliases"])
        self.assertEqual(profile["launchOptions"], "")
        self.assertEqual(profile["icon"], str(self.assets / "icon.png"))
        self.assertTrue(profile["current"])
        self.assertTrue(os.access(profile["wrapperPath"], os.X_OK))
        self.assertIn(
            f'exec {self.launcher} "$@"',
            Path(profile["wrapperPath"]).read_text(encoding="utf-8"),
        )

    def test_prepare_reports_missing_nested_desktop(self):
        self.launcher.unlink()

        self.assertFalse(self.manager.status()["available"])
        with self.assertRaises(FileNotFoundError):
            self.manager.prepare()

    def test_install_artwork_targets_auto_login_user_and_replaces_files(self):
        account_id = 12345
        steam_root = self.home / ".local/share/Steam"
        (steam_root / "config").mkdir(parents=True)
        (steam_root / "config/loginusers.vdf").write_text(
            '"users"\n{\n'
            f'  "{STEAM_ID64_BASE + account_id}"\n'
            "  {\n"
            '    "AutoLogin" "1"\n'
            '    "Timestamp" "42"\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        config = steam_root / f"userdata/{account_id}/config"
        grid = config / "grid"
        grid.mkdir(parents=True)
        (grid / "777p.png").write_bytes(b"custom")

        result = self.manager.install_artwork(777)

        self.assertEqual(result["installed"], 4)
        self.assertEqual(result["preserved"], 0)
        self.assertEqual(result["replaced"], 1)
        self.assertEqual(
            (grid / "777p.png").read_bytes(),
            b"capsule.png",
        )
        self.assertEqual(
            (grid / "777.png").read_bytes(),
            b"store-capsule.png",
        )
        self.assertEqual(
            (grid / "777_hero.png").read_bytes(),
            b"hero.png",
        )
        self.assertEqual(
            (grid / "777_logo.png").read_bytes(),
            b"logo.png",
        )

    def test_install_artwork_uses_most_recent_userdata_as_fallback(self):
        steam_root = self.home / ".local/share/Steam/userdata"
        older = steam_root / "100/config"
        newer = steam_root / "200/config"
        older.mkdir(parents=True)
        newer.mkdir(parents=True)
        (older / "localconfig.vdf").write_text("", encoding="utf-8")
        (newer / "localconfig.vdf").write_text("", encoding="utf-8")
        os.utime(older / "localconfig.vdf", (10, 10))
        os.utime(newer / "localconfig.vdf", (20, 20))

        result = self.manager.install_artwork(888)

        self.assertEqual(
            Path(result["gridDirectory"]),
            newer / "grid",
        )

    def test_install_artwork_validates_app_id(self):
        for invalid in (True, 0, -1, 0x100000000, "42"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.manager.install_artwork(invalid)


if __name__ == "__main__":
    unittest.main()

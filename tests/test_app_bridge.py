import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from app_bridge import AppBridgeManager, normalize_profile_id
from steam_artwork import STEAM_ID64_BASE


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AppBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.manager = AppBridgeManager(self.home, PROJECT_ROOT)

    def tearDown(self):
        self.temporary.cleanup()

    def test_profile_ids_are_safe_and_stable(self):
        self.assertEqual(normalize_profile_id(" Parsec Remote! "), "parsec-remote")
        self.assertEqual(normalize_profile_id("../../"), "")

    def test_profile_installs_autonomous_runner(self):
        prepared = self.manager.save_profile(
            {
                "id": "Example App",
                "name": "Example",
                "executable": "/usr/bin/true",
                "arguments": "",
                "workingDirectory": str(self.home),
                "clearSteamPreload": True,
                "forceX11": True,
            }
        )

        self.assertEqual(prepared["id"], "example-app")
        self.assertTrue(self.manager.runner_path.is_file())
        self.assertTrue(self.manager.runner_path.stat().st_mode & 0o100)
        profile_path = self.manager.profile_dir / "example-app.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        self.assertEqual(profile["command"], ["/usr/bin/true"])
        self.assertTrue(profile["clearSteamPreload"])
        self.assertTrue(profile["forceX11"])

        environment = {"HOME": str(self.home), "PATH": "/usr/bin:/bin"}
        completed = subprocess.run(
            [str(self.manager.runner_path), "example-app"],
            check=False,
            capture_output=True,
            env=environment,
            text=True,
            timeout=5,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_relative_executables_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            self.manager.save_profile(
                {
                    "name": "Unsafe",
                    "executable": "relative-command",
                }
            )

    def test_flatpak_commands_use_the_deck_user_data_directory(self):
        environment = self.manager._flatpak_environment()

        self.assertEqual(environment["HOME"], str(self.home))
        self.assertEqual(
            environment["XDG_DATA_HOME"],
            str(self.home / ".local/share"),
        )
        self.assertNotIn("LD_PRELOAD", environment)
        self.assertNotIn("LD_AUDIT", environment)

    def test_flatpak_installation_is_detected_from_its_exported_launcher(self):
        launcher = (
            self.home
            / ".local/share/flatpak/exports/share/applications"
            / "com.example.App.desktop"
        )
        launcher.parent.mkdir(parents=True)
        launcher.touch()

        self.assertTrue(self.manager._flatpak_installed("com.example.App"))

    def test_parsec_profile_tracks_real_daemon(self):
        prepared = self.manager.prepare_parsec()
        profile = json.loads(
            (
                self.manager.profile_dir / "parsec.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(prepared["name"], "Parsec")
        self.assertEqual(prepared["artworkId"], "parsec")
        self.assertEqual(profile["command"][0], "/usr/bin/flatpak")
        self.assertIn("com.parsecgaming.parsec", profile["command"])
        self.assertEqual(
            prepared["startDirectory"],
            str(
                self.home
                / ".local/share/flatpak/app/com.parsecgaming.parsec/current/"
                "active/files/bin"
            ),
        )
        self.assertEqual(
            profile["workingDirectory"],
            prepared["startDirectory"],
        )
        self.assertEqual(
            profile["waitForProcess"],
            "/app/extra/bin/parsecd",
        )

    def test_rustdesk_profile_replaces_the_legacy_wrapper(self):
        application_directory = (
            self.home / "Applications/RustDesk/usr/share/rustdesk"
        )
        application_directory.mkdir(parents=True)
        executable = application_directory / "rustdesk"
        executable.touch()

        prepared = self.manager.prepare_rustdesk()
        profile = json.loads(
            (
                self.manager.profile_dir / "rustdesk.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(prepared["name"], "RustDesk")
        self.assertEqual(prepared["artworkId"], "rustdesk")
        self.assertEqual(profile["command"], [str(executable)])
        self.assertEqual(profile["workingDirectory"], str(application_directory))
        self.assertTrue(profile["clearSteamPreload"])
        self.assertTrue(profile["forceX11"])
        self.assertEqual(
            profile["libraryPath"],
            str(application_directory / "compat-libs"),
        )

    def test_builtin_artwork_replaces_all_slots(self):
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
        grid = steam_root / f"userdata/{account_id}/config/grid"
        grid.mkdir(parents=True)
        (grid / "777p.png").write_bytes(b"custom")

        result = self.manager.install_artwork("parsec", 777)

        self.assertEqual(result["artworkId"], "parsec")
        self.assertEqual(result["installed"], 4)
        self.assertEqual(result["preserved"], 0)
        self.assertEqual(result["replaced"], 1)
        for destination, source in (
            ("777p.png", "capsule.png"),
            ("777.png", "grid.png"),
            ("777_hero.png", "hero.png"),
            ("777_logo.png", "logo.png"),
        ):
            with self.subTest(destination=destination):
                self.assertEqual(
                    (grid / destination).read_bytes(),
                    (
                        PROJECT_ROOT
                        / "assets/app-bridge/parsec"
                        / source
                    ).read_bytes(),
                )

    def test_artwork_is_limited_to_builtin_profiles(self):
        with self.assertRaisesRegex(ValueError, "not available"):
            self.manager.install_artwork("../../custom", 777)


if __name__ == "__main__":
    unittest.main()

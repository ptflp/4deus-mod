import base64
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app_bridge import AppBridgeManager, normalize_profile_id
from steam_artwork import STEAM_ID64_BASE


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = runpy.run_path(str(PROJECT_ROOT / "bin/4deus-app-bridge"))


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

    def test_installed_runner_is_refreshed_without_creating_a_new_one(self):
        self.assertFalse(self.manager.refresh_installed_runner())
        self.manager.save_profile(
            {
                "name": "Example",
                "executable": "/usr/bin/true",
            }
        )
        self.manager.runner_path.write_text("outdated", encoding="utf-8")

        self.assertTrue(self.manager.refresh_installed_runner())
        self.assertTrue(self.manager._runner_is_current())
        self.assertFalse(self.manager.refresh_installed_runner())

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
        self.assertTrue(profile["sanitizeSteamOverlay"])

    def test_chrome_profile_starts_flatpak_maximized(self):
        with patch.object(
            self.manager,
            "_flatpak_installed",
            return_value=True,
        ):
            prepared = self.manager.prepare_chrome()
        profile = json.loads(
            (self.manager.profile_dir / "chrome.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(prepared["name"], "Google Chrome")
        self.assertEqual(prepared["aliases"], ["Chrome"])
        self.assertEqual(prepared["artworkId"], "chrome")
        self.assertEqual(
            profile["command"],
            [
                "/usr/bin/flatpak",
                "run",
                "--branch=stable",
                "--arch=x86_64",
                "--command=chrome",
                "com.google.Chrome",
                "--start-maximized",
            ],
        )
        self.assertEqual(profile["workingDirectory"], str(self.home))
        self.assertTrue(profile["clearSteamPreload"])
        self.assertFalse(profile["sanitizeSteamOverlay"])
        self.assertFalse(profile["forceX11"])

    def test_terminal_profile_uses_konsole_without_steam_preloads(self):
        executable = self.home / "usr/bin/konsole"
        executable.parent.mkdir(parents=True)
        executable.touch()
        manager = AppBridgeManager(
            self.home,
            PROJECT_ROOT,
            terminal_executable=executable,
        )

        prepared = manager.prepare_terminal()
        profile = json.loads(
            (manager.profile_dir / "terminal.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(prepared["name"], "Terminal")
        self.assertEqual(prepared["artworkId"], "terminal")
        self.assertEqual(
            prepared["icon"],
            str(PROJECT_ROOT / "assets/app-bridge/terminal/icon.png"),
        )
        self.assertEqual(profile["command"], [str(executable)])
        self.assertEqual(profile["workingDirectory"], str(self.home))
        self.assertEqual(profile["waitForProcess"], str(executable))
        self.assertTrue(profile["clearSteamPreload"])
        self.assertFalse(profile["forceX11"])

    def test_runner_removes_only_wrong_class_steam_overlay(self):
        target = self.home / "target"
        overlay_32 = self.home / "ubuntu12_32/gameoverlayrenderer.so"
        overlay_64 = self.home / "ubuntu12_64/gameoverlayrenderer.so"
        unrelated_32 = self.home / "other/preload.so"
        for path, elf_class in (
            (target, 2),
            (overlay_32, 1),
            (overlay_64, 2),
            (unrelated_32, 1),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x7fELF" + bytes([elf_class]))

        preload = ":".join(
            (str(overlay_32), str(overlay_64), str(unrelated_32))
        )
        with patch.dict(os.environ, {"LD_PRELOAD": preload}):
            environment = RUNNER["build_environment"](
                {
                    "command": [str(target)],
                    "sanitizeSteamOverlay": True,
                }
            )

        self.assertEqual(
            environment["LD_PRELOAD"],
            f"{overlay_64}:{unrelated_32}",
        )

    def test_runner_full_cleanup_removes_preload_and_audit(self):
        with patch.dict(
            os.environ,
            {
                "LD_PRELOAD": "/steam/gameoverlayrenderer.so",
                "LD_AUDIT": "/steam/overlayaudit.so",
            },
        ):
            environment = RUNNER["build_environment"](
                {
                    "command": ["/usr/bin/true"],
                    "clearSteamPreload": True,
                    "sanitizeSteamOverlay": True,
                }
            )

        self.assertNotIn("LD_PRELOAD", environment)
        self.assertNotIn("LD_AUDIT", environment)

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
        self.assertEqual(
            base64.b64decode(result["liveArtwork"]["hero"]),
            (
                PROJECT_ROOT
                / "assets/app-bridge/parsec/hero.png"
            ).read_bytes(),
        )
        self.assertEqual(
            json.loads(result["liveLogoPosition"])["logoPosition"][
                "pinnedPosition"
            ],
            "BottomLeft",
        )
        self.assertTrue((grid / "777.json").is_file())

        custom_position = '{"nVersion":1,"custom":true}'
        (grid / "777.json").write_text(
            custom_position,
            encoding="utf-8",
        )
        repaired = self.manager.install_artwork("parsec", 777)
        self.assertIsNone(repaired["liveLogoPosition"])
        self.assertEqual(
            (grid / "777.json").read_text(encoding="utf-8"),
            custom_position,
        )

        terminal = self.manager.install_artwork("terminal", 778)
        self.assertEqual(terminal["artworkId"], "terminal")
        self.assertEqual(terminal["installed"], 4)
        self.assertEqual(
            (grid / "778p.png").read_bytes(),
            (
                PROJECT_ROOT
                / "assets/app-bridge/terminal/capsule.png"
            ).read_bytes(),
        )

        chrome = self.manager.install_artwork("chrome", 779)
        self.assertEqual(chrome["artworkId"], "chrome")
        self.assertEqual(chrome["installed"], 4)
        self.assertEqual(
            (grid / "779p.png").read_bytes(),
            (
                PROJECT_ROOT
                / "assets/app-bridge/chrome/capsule.png"
            ).read_bytes(),
        )

    def test_artwork_is_limited_to_builtin_profiles(self):
        with self.assertRaisesRegex(ValueError, "not available"):
            self.manager.install_artwork("../../custom", 777)


if __name__ == "__main__":
    unittest.main()

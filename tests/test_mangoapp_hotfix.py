import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mangoapp_hotfix import MangoHudFixManager


def elf_stub():
    header = bytearray(64)
    header[:4] = b"\x7fELF"
    header[4] = 2
    header[18:20] = (62).to_bytes(2, "little")
    return bytes(header)


class MangoHudFixManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.home = self.root / "home"
        self.plugin_root = self.root / "plugin"
        self.home.mkdir()
        (self.plugin_root / "bin").mkdir(parents=True)
        self.source = (
            self.plugin_root / "bin/mangoapp-fdinfo-guard.so"
        )
        self.source.write_bytes(elf_stub() + b"guard-v1")
        self.mangoapp = self.root / "mangoapp"
        self.mangoapp.write_bytes(b"mangoapp")
        self.systemctl = self.root / "systemctl"
        self.systemctl.write_bytes(b"systemctl")
        self.manager = MangoHudFixManager(
            self.home,
            self.plugin_root,
            mangoapp_path=self.mangoapp,
            systemctl_path=self.systemctl,
        )
        self.service_state = "active"
        self.commands = []

        def systemctl(*arguments, check=True):
            self.commands.append(arguments)
            if arguments[:1] == ("is-active",):
                return subprocess.CompletedProcess(
                    arguments,
                    0,
                    stdout=f"{self.service_state}\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout="",
                stderr="",
            )

        self.systemctl_patch = patch.object(
            self.manager,
            "_systemctl",
            side_effect=systemctl,
        )
        self.systemctl_patch.start()

    def tearDown(self):
        self.systemctl_patch.stop()
        self.temporary_directory.cleanup()

    def test_install_is_atomic_current_and_idempotent(self):
        result = self.manager.install()

        self.assertTrue(result["available"])
        self.assertTrue(result["installed"])
        self.assertTrue(result["current"])
        self.assertEqual(
            self.manager.library.read_bytes(),
            self.source.read_bytes(),
        )
        self.assertIn(
            "LD_PRELOAD=",
            self.manager.dropin.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            self.commands,
            [
                ("is-active", "gamescope-mangoapp.service"),
                ("daemon-reload",),
                ("restart", "gamescope-mangoapp.service"),
                ("is-active", "gamescope-mangoapp.service"),
            ],
        )

        self.commands.clear()
        self.manager.install()

        self.assertEqual(
            self.commands,
            [
                ("is-active", "gamescope-mangoapp.service"),
                ("is-active", "gamescope-mangoapp.service"),
            ],
        )

    def test_install_repairs_a_failed_service(self):
        self.service_state = "failed"

        self.manager.install()

        self.assertIn(
            ("reset-failed", "gamescope-mangoapp.service"),
            self.commands,
        )
        self.assertIn(
            ("restart", "gamescope-mangoapp.service"),
            self.commands,
        )

    def test_install_does_not_start_an_inactive_service(self):
        self.service_state = "inactive"

        self.manager.install()

        self.assertNotIn(
            ("restart", "gamescope-mangoapp.service"),
            self.commands,
        )

    def test_remove_cleans_only_managed_files_and_restarts_active_service(self):
        self.manager.install()
        unrelated = self.manager.dropin_directory / "90-user.conf"
        unrelated.write_text("[Service]\nNice=5\n", encoding="utf-8")
        self.commands.clear()

        result = self.manager.remove()

        self.assertFalse(result["installed"])
        self.assertFalse(self.manager.library.exists())
        self.assertFalse(self.manager.dropin.exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(
            self.commands,
            [
                ("is-active", "gamescope-mangoapp.service"),
                ("daemon-reload",),
                ("restart", "gamescope-mangoapp.service"),
                ("is-active", "gamescope-mangoapp.service"),
            ],
        )

    def test_install_migrates_the_known_legacy_dropin(self):
        self.manager.library.parent.mkdir(parents=True)
        self.manager.library.write_bytes(self.source.read_bytes())
        self.manager.dropin_directory.mkdir(parents=True)
        self.manager.legacy_dropin.write_text(
            self.manager._legacy_dropin_content(),
            encoding="utf-8",
        )

        before = self.manager.status()
        self.manager.install()

        self.assertTrue(before["installed"])
        self.assertFalse(before["current"])
        self.assertFalse(self.manager.legacy_dropin.exists())
        self.assertTrue(self.manager.dropin.exists())

    def test_install_repairs_modified_managed_dropin(self):
        self.manager.install()
        self.manager.dropin.write_text(
            "# Managed by 4deus Mod: MangoHud process FD guard\n"
            "[Service]\nEnvironment=LD_PRELOAD=/wrong/library.so\n",
            encoding="utf-8",
        )

        before = self.manager.status()
        after = self.manager.install()

        self.assertTrue(before["installed"])
        self.assertFalse(before["current"])
        self.assertTrue(after["current"])

    def test_unrelated_legacy_override_is_preserved(self):
        self.manager.dropin_directory.mkdir(parents=True)
        self.manager.legacy_dropin.write_text(
            "[Service]\nNice=10\n",
            encoding="utf-8",
        )

        self.manager.install()
        self.manager.remove()

        self.assertTrue(self.manager.legacy_dropin.exists())

    def test_remove_preserves_library_referenced_by_unmanaged_dropin(self):
        self.manager.library.parent.mkdir(parents=True)
        self.manager.library.write_bytes(self.source.read_bytes())
        self.manager.dropin_directory.mkdir(parents=True)
        unmanaged = self.manager.dropin_directory / "90-user.conf"
        unmanaged.write_text(
            "[Service]\n"
            f"Environment=LD_PRELOAD={self.manager.library}\n",
            encoding="utf-8",
        )

        self.manager.remove()

        self.assertTrue(unmanaged.exists())
        self.assertTrue(self.manager.library.exists())

    def test_rejects_a_non_x86_64_library(self):
        self.source.write_bytes(b"not an elf")

        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            self.manager.install()


if __name__ == "__main__":
    unittest.main()

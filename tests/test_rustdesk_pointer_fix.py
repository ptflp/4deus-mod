import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from rustdesk_pointer_fix import RustDeskPointerFixManager


def elf_stub():
    header = bytearray(64)
    header[:4] = b"\x7fELF"
    header[4] = 2
    header[18:20] = (62).to_bytes(2, "little")
    return bytes(header)


class RustDeskPointerFixManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.plugin_root = self.root / "plugin"
        self.units = self.root / "units"
        self.state = self.root / "state"
        self.proc = self.root / "proc"
        self.home.mkdir()
        (self.plugin_root / "bin").mkdir(parents=True)
        self.source = (
            self.plugin_root / "bin/rustdesk-uinput-pointer-sync.so"
        )
        self.source.write_bytes(elf_stub() + b"pointer-v1")
        application = (
            self.home / "Applications/RustDesk/usr/share/rustdesk"
        )
        application.mkdir(parents=True)
        (application / "compat-libs").mkdir()
        (application / "rustdesk").write_bytes(b"rustdesk")
        self.systemctl = self.root / "systemctl"
        self.systemctl.write_bytes(b"systemctl")
        self.manager = RustDeskPointerFixManager(
            self.home,
            self.plugin_root,
            systemctl_path=self.systemctl,
            system_unit_directory=self.units,
            state_directory=self.state,
            proc_root=self.proc,
        )
        self.service_state = "active"
        self.main_pid = 4321
        self.need_daemon_reload = False
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
            if arguments[:1] == ("show",):
                if "--property=NeedDaemonReload" in arguments:
                    return subprocess.CompletedProcess(
                        arguments,
                        0,
                        stdout=(
                            "yes\n"
                            if self.need_daemon_reload
                            else "no\n"
                        ),
                        stderr="",
                    )
                return subprocess.CompletedProcess(
                    arguments,
                    0,
                    stdout=f"{self.main_pid}\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout="",
                stderr="",
            )

        self.root_patch = patch.object(os, "geteuid", return_value=0)
        self.systemctl_patch = patch.object(
            self.manager,
            "_systemctl",
            side_effect=systemctl,
        )
        self.root_patch.start()
        self.systemctl_patch.start()

    def tearDown(self):
        self.systemctl_patch.stop()
        self.root_patch.stop()
        self.temporary.cleanup()

    def test_install_is_atomic_current_and_stages_without_restart(self):
        result = self.manager.install(restart=False)

        self.assertTrue(result["available"])
        self.assertTrue(result["installed"])
        self.assertTrue(result["current"])
        self.assertEqual(
            self.manager.library.read_bytes(),
            self.source.read_bytes(),
        )
        dropin = self.manager.dropin.read_text(encoding="utf-8")
        self.assertIn("ExecStart=", dropin)
        self.assertIn("LD_PRELOAD=", dropin)
        self.assertIn(
            f"WorkingDirectory={self.manager.application_directory}\n",
            dropin,
        )
        self.assertNotIn('WorkingDirectory="', dropin)
        self.assertNotIn(("restart", "rustdesk.service"), self.commands)

    def test_explicit_install_restarts_active_service_when_not_loaded(self):
        self.manager.install(restart=True)

        self.assertIn(("restart", "rustdesk.service"), self.commands)

    def test_explicit_install_does_not_restart_when_runtime_is_current(self):
        process = self.proc / str(self.main_pid)
        process.mkdir(parents=True)
        process.joinpath("maps").write_text(
            f"7f00-7f10 r-xp 0 00:00 0 {self.manager.source_library}\n",
            encoding="utf-8",
        )

        self.manager.install(restart=True)

        self.assertNotIn(("restart", "rustdesk.service"), self.commands)

    def test_install_recovers_a_pending_systemd_daemon_reload(self):
        self.manager.install()
        self.commands.clear()
        self.need_daemon_reload = True

        self.manager.install()

        self.assertIn(("daemon-reload",), self.commands)

    def test_remove_only_deletes_managed_dropin_and_library(self):
        self.manager.install()
        unrelated = self.manager.dropin_directory / "90-user.conf"
        unrelated.write_text("[Service]\nNice=5\n", encoding="utf-8")
        self.commands.clear()

        result = self.manager.remove()

        self.assertFalse(result["installed"])
        self.assertFalse(self.manager.library.exists())
        self.assertTrue(unrelated.exists())
        self.assertIn(("restart", "rustdesk.service"), self.commands)

    def test_non_root_install_is_rejected(self):
        with patch.object(os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(PermissionError, "root access"):
                self.manager.install()

    def test_rejects_missing_or_invalid_packaged_library(self):
        self.source.write_bytes(b"not an elf")

        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            self.manager.install()


if __name__ == "__main__":
    unittest.main()

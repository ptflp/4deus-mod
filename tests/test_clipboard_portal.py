from pathlib import Path
import tempfile
import unittest

from fourdeus_backend.nested_desktop.clipboard_portal import (
    active_flatpak_app_ids,
    DocumentPortalExporter,
    FileTransferPortal,
)


class _PortalInterface:
    def __init__(self):
        self.next_key = 1
        self.started = []
        self.added = []
        self.stopped = []

    def StartTransfer(self, options):
        key = f"key-{self.next_key}"
        self.next_key += 1
        self.started.append((key, options))
        return key

    def AddFiles(self, key, descriptors, options):
        self.added.append((key, tuple(descriptors), options))

    def StopTransfer(self, key):
        self.stopped.append(key)


class FileTransferPortalTests(unittest.TestCase):
    def test_replaces_and_retires_owned_portal_sessions(self):
        interface = _PortalInterface()
        portal = FileTransferPortal(
            interface=interface,
            fd_wrapper=lambda descriptor: descriptor,
        )
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory, "first.pdf")
            second = Path(directory, "second.zip")
            first.write_bytes(b"pdf")
            second.write_bytes(b"zip")

            self.assertEqual(portal.replace((first.as_uri(),)), b"key-1")
            self.assertEqual(portal.replace((second.as_uri(),)), b"key-2")

        self.assertEqual(
            [options for _key, options in interface.started],
            [
                {"writable": False, "autostop": False},
                {"writable": False, "autostop": False},
            ],
        )
        self.assertEqual([key for key, _fds, _options in interface.added], [
            "key-1",
            "key-2",
        ])
        self.assertEqual(interface.stopped, ["key-1"])

        portal.close()

        self.assertEqual(interface.stopped, ["key-1", "key-2"])

    def test_missing_files_do_not_leave_a_transfer_alive(self):
        interface = _PortalInterface()
        portal = FileTransferPortal(
            interface=interface,
            fd_wrapper=lambda descriptor: descriptor,
        )

        self.assertIsNone(portal.replace(("file:///missing/file.pdf",)))

        self.assertEqual(interface.stopped, ["key-1"])
        self.assertIsNone(portal.active_key)


class _DocumentsInterface:
    def __init__(self):
        self.added = []
        self.granted = []
        self.next_id = 1

    @staticmethod
    def GetMountPoint():
        return b"/run/user/1000/doc\0"

    def AddFull(self, descriptors, flags, app_id, permissions):
        descriptors = tuple(descriptors)
        for descriptor in descriptors:
            self.assert_open(descriptor)
        self.added.append((descriptors, flags, app_id, tuple(permissions)))
        doc_ids = []
        for _descriptor in descriptors:
            doc_ids.append(f"doc-{self.next_id}")
            self.next_id += 1
        return doc_ids, {"mountpoint": b"/run/user/1000/doc\0"}

    @staticmethod
    def assert_open(descriptor):
        import os

        os.fstat(descriptor)

    def GrantPermissions(self, doc_id, app_id, permissions):
        self.granted.append((doc_id, app_id, tuple(permissions)))


class DocumentPortalExporterTests(unittest.TestCase):
    def test_exports_files_for_every_active_flatpak(self):
        import os

        interface = _DocumentsInterface()
        exporter = DocumentPortalExporter(
            interface=interface,
            fd_wrapper=lambda descriptor: descriptor,
            app_ids_provider=lambda: (
                "com.google.Chrome",
                "com.slack.Slack",
                "com.google.Chrome",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory, "first file.pdf")
            second = Path(directory, "second.zip")
            first.write_bytes(b"pdf")
            second.write_bytes(b"zip")

            exported = exporter.export((first.as_uri(), second.as_uri()))

        self.assertEqual(exported, (
            "file:///run/user/1000/doc/doc-1/first%20file.pdf",
            "file:///run/user/1000/doc/doc-2/second.zip",
        ))
        descriptors, flags, app_id, permissions = interface.added[0]
        self.assertEqual(flags, 1)
        self.assertEqual(app_id, "com.google.Chrome")
        self.assertEqual(permissions, ("read",))
        self.assertEqual(interface.granted, [
            ("doc-1", "com.slack.Slack", ("read",)),
            ("doc-2", "com.slack.Slack", ("read",)),
        ])
        for descriptor in descriptors:
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_discovers_active_flatpak_ids_without_a_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime_dir = Path(directory)
            first = runtime_dir / ".flatpak" / "123" / "info"
            duplicate = runtime_dir / ".flatpak" / "456" / "info"
            malformed = runtime_dir / ".flatpak" / "789" / "info"
            first.parent.mkdir(parents=True)
            duplicate.parent.mkdir(parents=True)
            malformed.parent.mkdir(parents=True)
            first.write_text(
                "[Application]\nname=com.google.Chrome\n",
                encoding="utf-8",
            )
            duplicate.write_text(
                "[Application]\nname=com.google.Chrome\n",
                encoding="utf-8",
            )
            malformed.write_text(
                "[Application]\nname=../../invalid\n",
                encoding="utf-8",
            )

            self.assertEqual(
                active_flatpak_app_ids(runtime_dir),
                ("com.google.Chrome",),
            )


if __name__ == "__main__":
    unittest.main()

"""Developer-mode and trackpad-metrics Decky endpoints."""

import asyncio
import json
import os

from ..dependencies import logger


class DeveloperEndpointsMixin:
    async def get_developer_settings_status(self):
        monitor = self.trackpad_metrics
        metrics = (
            monitor.status()
            if monitor is not None
            else {
                "running": False,
                "devicePath": "",
                "sampleCount": 0,
                "retainedSeconds": 0,
                "capacitySeconds": 0,
                "sampleRateHz": 0,
                "latest": None,
                "captures": [],
                "error": "Trackpad metrics backend is unavailable",
            }
        )
        return {
            "developerMode": self.developer_mode,
            "trackpadMetricsEnabled": self.trackpad_metrics_enabled,
            "metrics": {
                "available": monitor is not None,
                **metrics,
            },
        }

    async def set_developer_mode(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_developer_settings_status(),
                "error": "Developer mode must be a boolean",
            }
        try:
            await asyncio.to_thread(
                self._save_developer_settings,
                enabled,
                self.trackpad_metrics_enabled,
            )
            self.developer_mode = enabled
            await asyncio.to_thread(self._sync_trackpad_metrics)
            logger.info(
                "Developer mode %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_developer_settings_status()
        except Exception as error:
            logger.exception("Failed to change developer mode")
            return {
                **await self.get_developer_settings_status(),
                "error": str(error),
            }

    async def set_trackpad_metrics_enabled(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_developer_settings_status(),
                "error": "Trackpad metrics enabled must be a boolean",
            }
        if enabled and not self.developer_mode:
            return {
                **await self.get_developer_settings_status(),
                "error": "Enable developer mode first",
            }
        try:
            await asyncio.to_thread(
                self._save_developer_settings,
                self.developer_mode,
                enabled,
            )
            self.trackpad_metrics_enabled = enabled
            await asyncio.to_thread(self._sync_trackpad_metrics)
            logger.info(
                "Trackpad metrics collection %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_developer_settings_status()
        except Exception as error:
            logger.exception("Failed to change trackpad metrics collection")
            return {
                **await self.get_developer_settings_status(),
                "error": str(error),
            }

    async def get_trackpad_metrics_window(
        self,
        capture_id: str = "",
        max_samples: int = 600,
    ):
        monitor = self.trackpad_metrics
        if monitor is None:
            return {
                "captureId": capture_id,
                "sampleCount": 0,
                "samples": [],
                "error": "Trackpad metrics backend is unavailable",
            }
        if not isinstance(capture_id, str) or not isinstance(
            max_samples,
            int,
        ):
            return {
                "captureId": "",
                "sampleCount": 0,
                "samples": [],
                "error": "Invalid trackpad metrics window request",
            }
        try:
            return await asyncio.to_thread(
                monitor.window,
                capture_id or None,
                max_samples,
            )
        except Exception as error:
            logger.exception("Failed to read trackpad metrics")
            return {
                "captureId": capture_id,
                "sampleCount": 0,
                "samples": [],
                "error": str(error),
            }

    async def capture_trackpad_metrics(self):
        monitor = self.trackpad_metrics
        if monitor is None:
            return {
                **await self.get_developer_settings_status(),
                "error": "Trackpad metrics backend is unavailable",
            }
        try:
            await asyncio.to_thread(monitor.capture)
            logger.info("Saved a manual trackpad metrics capture")
            return await self.get_developer_settings_status()
        except Exception as error:
            logger.exception("Failed to save trackpad metrics")
            return {
                **await self.get_developer_settings_status(),
                "error": str(error),
            }

    async def clear_trackpad_metrics_buffer(self):
        monitor = self.trackpad_metrics
        if monitor is not None:
            await asyncio.to_thread(monitor.clear)
        return await self.get_developer_settings_status()

    async def delete_trackpad_metrics_capture(self, capture_id: str):
        monitor = self.trackpad_metrics
        if monitor is None:
            return await self.get_developer_settings_status()
        if not isinstance(capture_id, str):
            return {
                **await self.get_developer_settings_status(),
                "error": "Invalid trackpad metrics capture ID",
            }
        try:
            await asyncio.to_thread(monitor.delete_capture, capture_id)
            return await self.get_developer_settings_status()
        except Exception as error:
            logger.exception("Failed to delete trackpad metrics capture")
            return {
                **await self.get_developer_settings_status(),
                "error": str(error),
            }

    def _sync_trackpad_metrics(self):
        monitor = self.trackpad_metrics
        if monitor is None:
            return
        metrics_enabled = (
            self.developer_mode
            and self.trackpad_metrics_enabled
        )
        recovery_enabled = False
        configure = getattr(monitor, "configure", None)
        if configure is not None:
            configure(
                metrics_enabled=metrics_enabled,
                recovery_enabled=recovery_enabled,
            )
        elif metrics_enabled or recovery_enabled:
            monitor.start()
        else:
            monitor.stop()

    def _load_developer_settings(self) -> tuple[bool, bool]:
        try:
            payload = json.loads(
                self.developer_settings_path.read_text(encoding="utf-8")
            )
            return (
                payload.get("developerMode", False) is True,
                payload.get("trackpadMetricsEnabled", False) is True,
            )
        except FileNotFoundError:
            return False, False
        except Exception:
            logger.exception("Failed to read developer settings")
            return False, False

    def _save_developer_settings(
        self,
        developer_mode: bool,
        trackpad_metrics_enabled: bool,
    ):
        path = self.developer_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "developerMode": developer_mode,
                    "trackpadMetricsEnabled": trackpad_metrics_enabled,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

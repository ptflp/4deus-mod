"""Controller recovery Decky endpoints."""

import asyncio
import json
import os
from pathlib import Path

from ..dependencies import (
    logger,
    power_cycle_steam_deck_controller,
    reinitialize_steam_deck_trackpad_driver,
)


class ControllerEndpointsMixin:
    async def get_controller_status(self):
        monitor = self.trackpad_metrics
        recovery = (
            monitor.recovery_status()
            if monitor is not None
            else {
                "enabled": self.trackpad_auto_recovery_enabled,
                "monitoring": False,
                "armed": False,
                "pending": False,
                "lastAttemptAtMs": 0,
                "lastSuccessAtMs": 0,
                "successCount": 0,
                "error": "Trackpad recovery backend is unavailable",
            }
        )
        return {
            "available": monitor is not None,
            "autoRecoveryEnabled": self.trackpad_auto_recovery_enabled,
            **recovery,
        }

    async def set_trackpad_auto_recovery_enabled(self, enabled: bool):
        if not isinstance(enabled, bool):
            return {
                **await self.get_controller_status(),
                "error": "Trackpad auto-recovery enabled must be a boolean",
            }
        try:
            await asyncio.to_thread(
                self._save_controller_settings,
                enabled,
            )
            self.trackpad_auto_recovery_enabled = enabled
            await asyncio.to_thread(self._sync_trackpad_metrics)
            logger.info(
                "Trackpad auto-recovery %s",
                "enabled" if enabled else "disabled",
            )
            return await self.get_controller_status()
        except Exception as error:
            logger.exception("Failed to change trackpad auto-recovery")
            return {
                **await self.get_controller_status(),
                "error": str(error),
            }

    async def reinitialize_trackpad_controller(self):
        try:
            path = await asyncio.to_thread(
                self._reinitialize_trackpad_controller,
            )
            return {
                **await self.get_controller_status(),
                "devicePath": str(path),
            }
        except Exception as error:
            logger.exception("Failed to reinitialize the trackpad controller")
            return {
                **await self.get_controller_status(),
                "error": str(error),
            }

    async def power_cycle_trackpad_controller(self, force: bool = False):
        if not isinstance(force, bool):
            return {
                **await self.get_controller_status(),
                "error": "Force must be a boolean",
            }
        try:
            path = await asyncio.to_thread(
                self._power_cycle_trackpad_controller,
                force,
            )
            status = await self.get_controller_status()
            status.pop("error", None)
            return {**status, "devicePath": str(path)}
        except Exception as error:
            logger.exception("Failed to power-cycle the trackpad controller")
            return {
                **await self.get_controller_status(),
                "error": str(error),
            }

    def _load_controller_settings(self) -> bool:
        try:
            payload = json.loads(
                self.controller_settings_path.read_text(encoding="utf-8")
            )
            return payload.get("trackpadAutoRecoveryEnabled", False) is True
        except FileNotFoundError:
            return False
        except Exception:
            logger.exception("Failed to read controller settings")
            return False

    def _save_controller_settings(self, enabled: bool):
        path = self.controller_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"trackpadAutoRecoveryEnabled": enabled},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def _recover_trackpad_controller(self, request_id: int) -> bool:
        path = self._power_cycle_trackpad_controller()
        logger.info(
            "Trackpad recovery request %d power-cycled USB controller at %s",
            request_id,
            path,
        )
        return True

    def _reinitialize_trackpad_controller(self) -> Path:
        reinitializer = reinitialize_steam_deck_trackpad_driver
        if reinitializer is None:
            raise RuntimeError(
                "Trackpad controller recovery backend is unavailable"
            )
        monitor = self.trackpad_metrics
        if monitor is not None:
            with monitor.lock:
                sample = monitor.raw_latest
            if sample is not None and (
                sample.left_touched
                or sample.left_pressed
                or sample.left_pressure > 0
                or sample.right_touched
                or sample.right_pressed
                or sample.right_pressure > 0
            ):
                raise RuntimeError(
                    "Release both trackpads before reinitialization"
                )
        device_path = (
            monitor.device_path
            if monitor is not None
            else None
        )
        return reinitializer(device_path=device_path)

    def _power_cycle_trackpad_controller(
        self,
        force: bool = False,
    ) -> Path:
        power_cycler = power_cycle_steam_deck_controller
        if power_cycler is None:
            raise RuntimeError(
                "Trackpad controller USB recovery backend is unavailable"
            )
        monitor = self.trackpad_metrics
        device_path = None
        if monitor is not None:
            with monitor.lock:
                sample = monitor.raw_latest
                device_path = monitor.device_path
            if not force and sample is not None and (
                sample.left_touched
                or sample.left_pressed
                or sample.left_pressure > 0
                or sample.right_touched
                or sample.right_pressed
                or sample.right_pressure > 0
            ):
                raise RuntimeError(
                    "Release both trackpads before the USB power cycle"
                )
        return power_cycler(device_path=device_path)

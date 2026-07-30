"""App Bridge and System Tools Decky endpoints."""

import asyncio

from ..dependencies import logger


class SystemToolsEndpointsMixin:
    async def get_app_bridge_status(self):
        if self.app_bridge is None:
            return {"error": "App Bridge backend is unavailable"}
        return self.app_bridge.status()

    async def list_app_bridge_applications(self):
        if self.app_bridge is None:
            return []
        return self.app_bridge.list_applications()

    async def save_app_bridge_profile(self, profile):
        if self.app_bridge is None:
            return {"error": "App Bridge backend is unavailable"}
        try:
            return self.app_bridge.save_profile(profile)
        except Exception as error:
            logger.exception("Failed to save App Bridge profile")
            return {"error": str(error)}

    async def prepare_parsec_app_bridge(self):
        if self.app_bridge is None:
            return {"error": "App Bridge backend is unavailable"}
        try:
            return self.app_bridge.prepare_parsec()
        except Exception as error:
            logger.exception("Failed to prepare Parsec App Bridge profile")
            return {"error": str(error)}

    async def prepare_rustdesk_app_bridge(self):
        if self.app_bridge is None:
            return {"error": "App Bridge backend is unavailable"}
        try:
            prepared = self.app_bridge.prepare_rustdesk()
            if self.rustdesk_pointer_fix_enabled:
                await self._install_rustdesk_pointer_fix(restart=True)
            return prepared
        except Exception as error:
            logger.exception("Failed to prepare RustDesk App Bridge profile")
            return {"error": str(error)}

    async def install_app_bridge_artwork(
        self,
        artwork_id: str,
        app_id: int,
    ):
        if self.app_bridge is None:
            return {
                "error": "App Bridge backend is unavailable",
                "installed": 0,
                "preserved": 0,
            }
        try:
            result = await asyncio.to_thread(
                self.app_bridge.install_artwork,
                artwork_id,
                app_id,
            )
            logger.info(
                "Installed App Bridge artwork %s for non-Steam AppID %s",
                artwork_id,
                app_id,
            )
            return result
        except Exception as error:
            logger.exception(
                "Failed to install App Bridge artwork %s for AppID %s",
                artwork_id,
                app_id,
            )
            return {
                "error": str(error),
                "installed": 0,
                "preserved": 0,
            }

    async def get_mangohud_fix_status(self):
        if self.mangohud_fix is None:
            return {
                "available": False,
                "current": False,
                "error": "System Tools backend is unavailable",
                "installed": False,
                "libraryPath": "",
                "serviceState": "unknown",
            }
        try:
            return await asyncio.to_thread(self.mangohud_fix.status)
        except Exception as error:
            logger.exception("Failed to read MangoHud fix status")
            return self._mangohud_fix_error(error)

    async def install_mangohud_fix(self):
        if self.mangohud_fix is None:
            return await self.get_mangohud_fix_status()
        try:
            result = await asyncio.to_thread(self.mangohud_fix.install)
            logger.info("Installed or repaired MangoHud process FD guard")
            return result
        except Exception as error:
            logger.exception("Failed to install MangoHud process FD guard")
            return self._mangohud_fix_error(error)

    async def remove_mangohud_fix(self):
        if self.mangohud_fix is None:
            return await self.get_mangohud_fix_status()
        try:
            result = await asyncio.to_thread(self.mangohud_fix.remove)
            logger.info("Removed MangoHud process FD guard")
            return result
        except Exception as error:
            logger.exception("Failed to remove MangoHud process FD guard")
            return self._mangohud_fix_error(error)

    def _mangohud_fix_error(self, error):
        try:
            status = self.mangohud_fix.status()
        except Exception:
            status = {
                "available": False,
                "current": False,
                "installed": False,
                "libraryPath": "",
                "serviceState": "unknown",
            }
        return {
            **status,
            "error": str(error),
        }

    async def get_steamos_application_status(self):
        if self.steamos_application is None:
            return {
                "available": False,
                "current": False,
                "error": "SteamOS application backend is unavailable",
                "icon": "",
                "wrapperInstalled": False,
                "wrapperPath": "",
            }
        try:
            return self.steamos_application.status()
        except Exception as error:
            logger.exception("Failed to read SteamOS application status")
            return self._steamos_application_error(error)

    async def prepare_steamos_application(self):
        if self.steamos_application is None:
            return await self.get_steamos_application_status()
        try:
            result = await asyncio.to_thread(self.steamos_application.prepare)
            logger.info("Prepared the SteamOS Nested Desktop wrapper")
            return result
        except Exception as error:
            logger.exception("Failed to prepare the SteamOS application")
            return self._steamos_application_error(error)

    async def install_steamos_application_artwork(self, app_id: int):
        if self.steamos_application is None:
            return {
                "error": "SteamOS application backend is unavailable",
                "installed": 0,
                "preserved": 0,
            }
        try:
            result = await asyncio.to_thread(
                self.steamos_application.install_artwork,
                app_id,
            )
            logger.info(
                "Installed SteamOS artwork for non-Steam AppID %s",
                app_id,
            )
            return result
        except Exception as error:
            logger.exception(
                "Failed to install SteamOS artwork for AppID %s",
                app_id,
            )
            return {
                "error": str(error),
                "installed": 0,
                "preserved": 0,
            }

    def _steamos_application_error(self, error):
        try:
            status = self.steamos_application.status()
        except Exception:
            status = {
                "available": False,
                "current": False,
                "icon": "",
                "wrapperInstalled": False,
                "wrapperPath": "",
            }
        return {
            **status,
            "error": str(error),
        }

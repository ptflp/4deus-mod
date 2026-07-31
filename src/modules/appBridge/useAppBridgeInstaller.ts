import { useState } from "react";

import type { Strings } from "../../core/localization";
import type { SettingsStore } from "../../core/settings";
import { ensureAppBridgeShortcut } from "./steamShortcuts";
import type {
  AppBridgeApi,
  PreparedAppBridgeProfile,
} from "./types";

interface AppBridgeInstaller {
  busy: boolean;
  install(
    prepare: () => Promise<PreparedAppBridgeProfile>,
  ): Promise<void>;
  message: string;
}

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

export const useAppBridgeInstaller = (
  api: AppBridgeApi,
  settings: SettingsStore,
  strings: Strings,
): AppBridgeInstaller => {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const installPrepared = async (
    prepared: PreparedAppBridgeProfile,
  ): Promise<void> => {
    if (prepared.error)
      throw new Error(prepared.error);
    const shortcutIds = settings.getSnapshot().appBridge.shortcutAppIds;
    const appId = await ensureAppBridgeShortcut(
      prepared,
      shortcutIds[prepared.id],
    );
    if (prepared.artworkId) {
      const artwork = await api.installArtwork(prepared.artworkId, appId);
      if (artwork.error)
        throw new Error(artwork.error);
    }
    settings.updateAppBridge({
      shortcutAppIds: {
        ...shortcutIds,
        [prepared.id]: appId,
      },
    });
    setMessage(`${strings.appBridgeReady}: ${prepared.name}`);
  };

  const install = async (
    prepare: () => Promise<PreparedAppBridgeProfile>,
  ): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      await installPrepared(await prepare());
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return { busy, install, message };
};

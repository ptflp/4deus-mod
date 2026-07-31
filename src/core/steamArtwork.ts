export interface SteamArtworkPayload {
  capsule?: string;
  grid?: string;
  hero?: string;
  logo?: string;
}

export interface SteamArtworkInstallResult {
  error?: string;
  liveArtwork?: SteamArtworkPayload;
  liveLogoPosition?: string;
}

type SteamArtworkAssetType = Parameters<
  typeof window.SteamClient.Apps.SetCustomArtworkForApp
>[3];

const ARTWORK_ASSET_TYPES: ReadonlyArray<[
  keyof SteamArtworkPayload,
  SteamArtworkAssetType,
]> = [
  ["capsule", 0 as SteamArtworkAssetType],
  ["hero", 1 as SteamArtworkAssetType],
  ["logo", 2 as SteamArtworkAssetType],
  ["grid", 3 as SteamArtworkAssetType],
];

const ARTWORK_CLEAR_DELAY_MS = 500;

export interface SteamArtworkRefreshResult {
  attempted: number;
  cleared: number;
  updated: number;
}

export const refreshSteamArtwork = async (
  appId: number,
  artwork: SteamArtworkPayload | undefined,
  logoPosition?: string,
): Promise<SteamArtworkRefreshResult> => {
  if (!artwork || !Number.isInteger(appId) || appId < 1)
    return { attempted: 0, cleared: 0, updated: 0 };

  const entries = ARTWORK_ASSET_TYPES.flatMap(([slot, assetType]) => {
    const image = artwork[slot];
    return image ? [{ assetType, image }] : [];
  });
  const attempted = entries.length;

  const apps = window.SteamClient?.Apps;
  if (
    typeof apps?.ClearCustomArtworkForApp !== "function"
    || typeof apps.SetCustomArtworkForApp !== "function"
  ) {
    return { attempted, cleared: 0, updated: 0 };
  }

  const clearResults = await Promise.all(entries.map(({ assetType }) =>
    Promise.resolve()
      .then(() => apps.ClearCustomArtworkForApp(appId, assetType))
      .then(() => true)
      .catch(() => false)
  ));
  const cleared = clearResults.filter(Boolean).length;
  if (cleared > 0) {
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, ARTWORK_CLEAR_DELAY_MS);
    });
  }

  const updateResults = await Promise.all(entries.map((entry, index) => {
    if (!clearResults[index])
      return Promise.resolve(0);
    return Promise.resolve()
      .then(() => apps.SetCustomArtworkForApp(
        appId,
        entry.image,
        "png",
        entry.assetType,
      ))
      .then(() => 1)
      .catch(() => 0);
  }));
  if (
    logoPosition
    && typeof apps.SetCustomLogoPositionForApp === "function"
  ) {
    await apps.SetCustomLogoPositionForApp(appId, logoPosition)
      .catch(() => undefined);
  }
  return {
    attempted,
    cleared,
    updated: updateResults.reduce(
      (total, updated) => total + updated,
      0,
    ),
  };
};

export const installSteamArtworkWithLiveRefresh = async (
  appId: number,
  install: () => Promise<SteamArtworkInstallResult>,
): Promise<void> => {
  const artwork = await install();
  if (artwork.error)
    throw new Error(artwork.error);
  const refresh = await refreshSteamArtwork(
    appId,
    artwork.liveArtwork,
    artwork.liveLogoPosition,
  );
  if (refresh.cleared <= refresh.updated)
    return;
  const restored = await install();
  if (restored.error)
    throw new Error(restored.error);
};

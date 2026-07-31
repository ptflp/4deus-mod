import assert from "node:assert/strict";
import test from "node:test";

import {
  installSteamArtworkWithLiveRefresh,
  refreshSteamArtwork,
} from "../src/core/steamArtwork.ts";

const installArtworkMock = (
  update: (...args: unknown[]) => Promise<void>,
  updateLogoPosition?: (...args: unknown[]) => Promise<void>,
  clear: (...args: unknown[]) => Promise<void> = async () => undefined,
): void => {
  (globalThis as unknown as { window: unknown }).window = {
    SteamClient: {
      Apps: {
        ClearCustomArtworkForApp: clear,
        SetCustomArtworkForApp: update,
        SetCustomLogoPositionForApp: updateLogoPosition,
      },
    },
    setTimeout: (callback: () => void) => callback(),
  };
};

test("live Steam artwork uses the matching library asset types", async () => {
  const calls: unknown[][] = [];
  installArtworkMock(async (...args: unknown[]) => {
    calls.push(args);
  });

  const updated = await refreshSteamArtwork(42, {
    capsule: "portrait",
    grid: "landscape",
    hero: "background",
    logo: "transparent-logo",
  });

  assert.deepEqual(updated, {
    attempted: 4,
    cleared: 4,
    updated: 4,
  });
  assert.deepEqual(calls, [
    [42, "portrait", "png", 0],
    [42, "background", "png", 1],
    [42, "transparent-logo", "png", 2],
    [42, "landscape", "png", 3],
  ]);
});

test("live artwork failures remain a best-effort cache refresh", async () => {
  installArtworkMock(async (...args: unknown[]) => {
    if (args[3] === 1)
      throw new Error("unsupported");
  });

  assert.deepEqual(await refreshSteamArtwork(42, {
    capsule: "portrait",
    hero: "background",
  }), { attempted: 2, cleared: 2, updated: 1 });
  assert.deepEqual(await refreshSteamArtwork(0, {
    capsule: "portrait",
  }), { attempted: 0, cleared: 0, updated: 0 });
});

test("a new shortcut receives its default logo position", async () => {
  const positionCalls: unknown[][] = [];
  installArtworkMock(
    async () => undefined,
    async (...args: unknown[]) => {
      positionCalls.push(args);
    },
  );

  assert.deepEqual(await refreshSteamArtwork(
    42,
    { logo: "transparent-logo" },
    '{"nVersion":1}',
  ), { attempted: 1, cleared: 1, updated: 1 });
  assert.deepEqual(positionCalls, [[42, '{"nVersion":1}']]);
});

test("a failed live update restores the disk artwork", async () => {
  let installs = 0;
  installArtworkMock(async (...args: unknown[]) => {
    if (args[3] === 1)
      throw new Error("native update failed");
  });

  await installSteamArtworkWithLiveRefresh(42, async () => {
    installs += 1;
    return {
      liveArtwork: {
        capsule: "portrait",
        hero: "background",
      },
    };
  });

  assert.equal(installs, 2);
});

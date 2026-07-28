import assert from "node:assert/strict";
import test from "node:test";

import { appBridgeTranslations } from "../src/core/appBridgeTranslations.ts";

const APP_BRIDGE_KEYS = [
  "addOrFixApplication",
  "addOrFixParsec",
  "addOrFixRustDesk",
  "appBridge",
  "appBridgeApplications",
  "appBridgeArguments",
  "appBridgeClearSteamRuntime",
  "appBridgeEnabledDescription",
  "appBridgeExecutable",
  "appBridgeForceX11",
  "appBridgeLibraryPath",
  "appBridgeLoadApplications",
  "appBridgeName",
  "appBridgeParsecDescription",
  "appBridgeQuickSetup",
  "appBridgeReady",
  "appBridgeRustDeskDescription",
  "appBridgeSelectApplication",
  "appBridgeTrackProcess",
  "appBridgeWorkingDirectory",
] as const;

test("App Bridge has complete translations for every Steam locale", () => {
  const expectedLanguages = [
    "arabic", "brazilian", "bulgarian", "czech", "danish", "dutch",
    "finnish", "french", "german", "greek", "hungarian", "indonesian",
    "italian", "japanese", "koreana", "latam", "malay", "norwegian",
    "polish", "portuguese", "romanian", "schinese", "spanish", "swedish",
    "tchinese", "thai", "turkish", "ukrainian", "vietnamese",
  ];
  assert.deepEqual(
    Object.keys(appBridgeTranslations).sort(),
    expectedLanguages.sort(),
  );

  for (const [language, strings] of Object.entries(appBridgeTranslations)) {
    for (const key of APP_BRIDGE_KEYS)
      assert.ok(strings[key].trim(), `${language}.${key}`);
  }
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { appBridgeTranslations } from "../src/core/appBridgeTranslations.ts";
import { nestedDesktopTranslations } from "../src/core/nestedDesktopTranslations.ts";
import { systemToolsTranslations } from "../src/core/systemToolsTranslations.ts";

const GETTING_STARTED_ANCHORS: Record<string, string> = {
  english: "en",
  arabic: "ar",
  brazilian: "pt-br",
  bulgarian: "bg",
  czech: "cs",
  danish: "da",
  dutch: "nl",
  finnish: "fi",
  french: "fr",
  german: "de",
  greek: "el",
  hungarian: "hu",
  indonesian: "id",
  italian: "it",
  japanese: "ja",
  koreana: "ko",
  latam: "es-419",
  malay: "ms",
  norwegian: "no",
  polish: "pl",
  portuguese: "pt",
  romanian: "ro",
  russian: "ru",
  schinese: "zh-cn",
  spanish: "es",
  swedish: "sv",
  tchinese: "zh-tw",
  thai: "th",
  turkish: "tr",
  ukrainian: "uk",
  vietnamese: "vi",
};

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

const SYSTEM_TOOLS_KEYS = [
  "systemTools",
  "systemToolsDescription",
  "systemToolsStatus",
  "systemToolsLoading",
  "mangoHudFix",
  "mangoHudFixDescription",
  "mangoHudFixInstalled",
  "mangoHudFixNeedsRepair",
  "mangoHudFixNotInstalled",
  "mangoHudFixUnavailable",
  "installOrRepairMangoHudFix",
  "removeMangoHudFix",
  "mangoHudFixApplied",
  "mangoHudFixRemoved",
  "steamOsApplication",
  "steamOsApplicationDescription",
  "addOrRepairSteamOsApplication",
  "steamOsApplicationReady",
  "nestedDesktopMouseBridge",
  "nestedDesktopMouseBridgeDescription",
  "nestedDesktopTrackpadInertia",
  "nestedDesktopTrackpadInertiaDescription",
  "rustDeskPointerFix",
  "rustDeskPointerFixDescription",
  "rustDeskScrollInertia",
  "rustDeskScrollInertiaDescription",
] as const;

test("System Tools has complete translations for every Steam locale", () => {
  const expectedLanguages = [
    "arabic", "brazilian", "bulgarian", "czech", "danish", "dutch",
    "finnish", "french", "german", "greek", "hungarian", "indonesian",
    "italian", "japanese", "koreana", "latam", "malay", "norwegian",
    "polish", "portuguese", "romanian", "russian", "schinese", "spanish",
    "swedish", "tchinese", "thai", "turkish", "ukrainian", "vietnamese",
  ];
  assert.deepEqual(
    Object.keys(systemToolsTranslations).sort(),
    expectedLanguages.sort(),
  );

  for (const [language, strings] of Object.entries(systemToolsTranslations)) {
    for (const key of SYSTEM_TOOLS_KEYS)
      assert.ok(strings[key].trim(), `${language}.${key}`);
  }
});

const NESTED_DESKTOP_KEYS = [
  "nestedDesktopHotkeys",
  "nestedDesktopHotkeysDescription",
  "nestedDesktopHotkeysEnabled",
  "nestedDesktopHotkeysEnabledDescription",
  "resetNestedDesktopHotkeys",
  "nestedDesktopHotkeysReset",
] as const;

test("Nested Desktop bindings have complete Steam locale translations", () => {
  const expectedLanguages = [
    "english", "arabic", "brazilian", "bulgarian", "czech", "danish",
    "dutch", "finnish", "french", "german", "greek", "hungarian",
    "indonesian", "italian", "japanese", "koreana", "latam", "malay",
    "norwegian", "polish", "portuguese", "romanian", "russian", "schinese",
    "spanish", "swedish", "tchinese", "thai", "turkish", "ukrainian",
    "vietnamese",
  ];
  assert.deepEqual(
    Object.keys(nestedDesktopTranslations).sort(),
    expectedLanguages.sort(),
  );

  for (const [language, strings] of Object.entries(
    nestedDesktopTranslations,
  )) {
    for (const key of NESTED_DESKTOP_KEYS)
      assert.ok(strings[key].trim(), `${language}.${key}`);
  }
});

test("Getting Started covers every Steam locale", () => {
  const guide = readFileSync(
    new URL("../docs/GETTING_STARTED.md", import.meta.url),
    "utf8",
  );
  assert.deepEqual(
    Object.keys(GETTING_STARTED_ANCHORS).sort(),
    ["english", ...Object.keys(systemToolsTranslations)].sort(),
  );

  for (const anchor of Object.values(GETTING_STARTED_ANCHORS)) {
    assert.ok(
      guide.includes(`](#${anchor})`),
      `Missing language link for ${anchor}`,
    );
    assert.ok(
      guide.includes(`<a id="${anchor}"></a>`),
      `Missing language section for ${anchor}`,
    );
  }

  const downloadUrl =
    "https://github.com/ptflp/4deus-mod/releases/latest/download/"
    + "4deusMod.zip";
  assert.equal(
    guide.split(downloadUrl).length - 1,
    Object.keys(GETTING_STARTED_ANCHORS).length,
  );
});

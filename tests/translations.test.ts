import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  appBridgeFeatureTranslations,
} from "../src/core/appBridgeFeatureTranslations.ts";
import { appBridgeTranslations } from "../src/core/appBridgeTranslations.ts";
import { commonTranslations } from "../src/core/commonTranslations.ts";
import { developerTranslations } from "../src/core/developerTranslations.ts";
import { keyboardTranslations } from "../src/core/keyboardTranslations.ts";
import {
  STEAM_LANGUAGE_ALIASES,
  STEAM_LANGUAGES,
} from "../src/core/locales.ts";
import {
  nestedDesktopControlTranslations,
} from "../src/core/nestedDesktopControlTranslations.ts";
import {
  nestedDesktopTranslations,
} from "../src/core/nestedDesktopTranslations.ts";
import {
  systemInputTranslations,
} from "../src/core/systemInputTranslations.ts";
import {
  systemToolsTranslations,
} from "../src/core/systemToolsTranslations.ts";

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

const TRANSLATION_MODULES = [
  ["common UI", commonTranslations],
  ["keyboard", keyboardTranslations],
  ["developer tools", developerTranslations],
  ["App Bridge", appBridgeTranslations],
  ["App Bridge features", appBridgeFeatureTranslations],
  ["System Tools", systemToolsTranslations],
  ["system input", systemInputTranslations],
  ["Nested Desktop", nestedDesktopTranslations],
  ["Nested Desktop controls", nestedDesktopControlTranslations],
] as const;

const sortedSteamLanguages = (): string[] => [...STEAM_LANGUAGES].sort();

const stringEntries = (value: object): Array<[string, string]> =>
  Object.entries(value) as Array<[string, string]>;

test("every UI module has the same complete set of Steam locales", () => {
  for (const [moduleName, record] of TRANSLATION_MODULES) {
    assert.deepEqual(
      Object.keys(record).sort(),
      sortedSteamLanguages(),
      moduleName,
    );
  }
});

test("every locale has every key and no blank UI text", () => {
  for (const [moduleName, record] of TRANSLATION_MODULES) {
    const englishKeys = Object.keys(record.english).sort();
    for (const language of STEAM_LANGUAGES) {
      const strings = record[language];
      assert.deepEqual(
        Object.keys(strings).sort(),
        englishKeys,
        `${moduleName}.${language} keys`,
      );
      for (const [key, value] of stringEntries(strings)) {
        assert.equal(typeof value, "string", `${language}.${key} type`);
        assert.ok(value.trim(), `${language}.${key}`);
      }
    }
  }
});

test("translation modules own disjoint UI keys", () => {
  const owners = new Map<string, string>();
  for (const [moduleName, record] of TRANSLATION_MODULES) {
    for (const key of Object.keys(record.english)) {
      assert.equal(
        owners.get(key),
        undefined,
        `${key} is duplicated by ${owners.get(key)} and ${moduleName}`,
      );
      owners.set(key, moduleName);
    }
  }
});

test("all composed locales expose one stable UI contract", () => {
  const compose = (language: typeof STEAM_LANGUAGES[number]) =>
    Object.assign(
      {},
      ...TRANSLATION_MODULES.map(([, record]) => record[language]),
    ) as Record<string, string>;
  const englishKeys = Object.keys(compose("english")).sort();

  for (const language of STEAM_LANGUAGES) {
    const strings = compose(language);
    assert.deepEqual(Object.keys(strings).sort(), englishKeys, language);
    assert.ok(
      Object.values(strings).every((value) => value.trim().length > 0),
      `${language} contains blank UI text`,
    );
  }

  assert.deepEqual(STEAM_LANGUAGE_ALIASES, {
    sc_schinese: "schinese",
  });
});

test("RustDesk auto-focus warnings identify the Steam PIN bypass", () => {
  for (const [language, strings] of Object.entries(
    systemToolsTranslations,
  )) {
    assert.ok(
      strings.rustDeskFocusOnInputDescription.startsWith("⚠"),
      `${language}.rustDeskFocusOnInputDescription warning`,
    );
    assert.match(
      strings.rustDeskFocusOnInputDescription,
      /PIN/iu,
      `${language}.rustDeskFocusOnInputDescription PIN`,
    );
  }
});

test("Getting Started covers every Steam locale", () => {
  const guide = readFileSync(
    new URL("../docs/GETTING_STARTED.md", import.meta.url),
    "utf8",
  );
  assert.deepEqual(
    Object.keys(GETTING_STARTED_ANCHORS).sort(),
    sortedSteamLanguages(),
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

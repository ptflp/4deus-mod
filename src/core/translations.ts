import {
  appBridgeFeatureTranslations,
  type AppBridgeFeatureTranslation,
} from "./appBridgeFeatureTranslations";
import {
  appBridgeTranslations,
  type AppBridgeTranslation,
} from "./appBridgeTranslations";
import {
  commonTranslations,
  type CommonTranslation,
} from "./commonTranslations";
import {
  developerTranslations,
  type DeveloperTranslation,
} from "./developerTranslations";
import {
  keyboardTranslations,
  type KeyboardTranslation,
} from "./keyboardTranslations";
import {
  STEAM_LANGUAGE_ALIASES,
  STEAM_LANGUAGES,
  type SteamLanguage,
} from "./locales";
import {
  nestedDesktopControlTranslations,
  type NestedDesktopControlTranslation,
} from "./nestedDesktopControlTranslations";
import {
  nestedDesktopTranslations,
  type NestedDesktopTranslation,
} from "./nestedDesktopTranslations";
import {
  systemInputTranslations,
  type SystemInputTranslation,
} from "./systemInputTranslations";
import {
  systemToolsTranslations,
  type SystemToolsTranslation,
} from "./systemToolsTranslations";

export type Strings =
  & AppBridgeFeatureTranslation
  & AppBridgeTranslation
  & CommonTranslation
  & DeveloperTranslation
  & KeyboardTranslation
  & NestedDesktopControlTranslation
  & NestedDesktopTranslation
  & SystemInputTranslation
  & SystemToolsTranslation;

const requireTranslation = <T>(
  record: Readonly<Record<string, T>>,
  language: SteamLanguage,
  owner: string,
): T => {
  const translation = record[language];
  if (!translation)
    throw new Error(`Missing ${owner} translation for ${language}`);
  return translation;
};

const buildTranslation = (language: SteamLanguage): Strings => ({
  ...requireTranslation(
    commonTranslations,
    language,
    "common UI",
  ),
  ...requireTranslation(
    keyboardTranslations,
    language,
    "keyboard",
  ),
  ...requireTranslation(
    developerTranslations,
    language,
    "developer tools",
  ),
  ...requireTranslation(
    appBridgeTranslations,
    language,
    "App Bridge",
  ),
  ...requireTranslation(
    appBridgeFeatureTranslations,
    language,
    "App Bridge features",
  ),
  ...requireTranslation(
    systemToolsTranslations,
    language,
    "System Tools",
  ),
  ...requireTranslation(
    systemInputTranslations,
    language,
    "system input",
  ),
  ...requireTranslation(
    nestedDesktopTranslations,
    language,
    "Nested Desktop",
  ),
  ...requireTranslation(
    nestedDesktopControlTranslations,
    language,
    "Nested Desktop controls",
  ),
});

const supportedLanguages = Object.fromEntries(
  STEAM_LANGUAGES.map((language) => [language, true]),
) as Record<SteamLanguage, true>;

const translationCache = new Map<SteamLanguage, Strings>();

const resolveLanguage = (language: string): SteamLanguage => {
  const alias = STEAM_LANGUAGE_ALIASES[language];
  if (alias)
    return alias;
  return Object.prototype.hasOwnProperty.call(supportedLanguages, language)
    ? language as SteamLanguage
    : "english";
};

export const getTranslation = (language: string): Strings => {
  const resolved = resolveLanguage(language);
  const cached = translationCache.get(resolved);
  if (cached)
    return cached;
  const translation = buildTranslation(resolved);
  translationCache.set(resolved, translation);
  return translation;
};

export const english = getTranslation("english");

export const STEAM_LANGUAGES = [
  "english",
  "arabic",
  "brazilian",
  "bulgarian",
  "czech",
  "danish",
  "dutch",
  "finnish",
  "french",
  "german",
  "greek",
  "hungarian",
  "indonesian",
  "italian",
  "japanese",
  "koreana",
  "latam",
  "malay",
  "norwegian",
  "polish",
  "portuguese",
  "romanian",
  "russian",
  "schinese",
  "spanish",
  "swedish",
  "tchinese",
  "thai",
  "turkish",
  "ukrainian",
  "vietnamese",
] as const;

export type SteamLanguage = typeof STEAM_LANGUAGES[number];

export const STEAM_LANGUAGE_ALIASES: Readonly<Record<string, SteamLanguage>> = {
  sc_schinese: "schinese",
};

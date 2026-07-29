import { useEffect, useState } from "react";

import { english, translations, type Strings } from "./translations";

const steamString = (token: string): string | undefined =>
  window.LocalizationManager?.m_mapTokens?.get(token);

const getStrings = (language: string): Strings => {
  const selected = translations[language] ?? english;
  return {
    ...selected,
    keyboard: steamString("Settings_Page_Keyboard") ?? selected.keyboard,
    hotkeys: steamString("Settings_InGame_Hotkeys") ?? selected.hotkeys,
    automatic: steamString("Broadcast_AutomaticResolution")
      ?? selected.automatic,
  };
};

export type { Strings };

export const useStrings = (): Strings => {
  const [strings, setStrings] = useState(() => getStrings("english"));

  useEffect(() => {
    window.SteamClient.Settings.GetCurrentLanguage()
      .then((language) => setStrings(getStrings(language)))
      .catch((error) => {
        console.warn("[4deus Mod] Failed to read Steam language", error);
      });
  }, []);

  return strings;
};

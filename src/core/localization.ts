import { useSyncExternalStore } from "react";

import { getTranslation, type Strings } from "./translations";

const steamString = (token: string): string | undefined =>
  window.LocalizationManager?.m_mapTokens?.get(token);

const getStrings = (language: string): Strings => {
  const selected = getTranslation(language);
  return {
    ...selected,
    keyboard: steamString("Settings_Page_Keyboard") ?? selected.keyboard,
    hotkeys: steamString("Settings_InGame_Hotkeys") ?? selected.hotkeys,
    automatic: steamString("Broadcast_AutomaticResolution")
      ?? selected.automatic,
  };
};

export type { Strings };

type Listener = () => void;

let currentStrings = getStrings("english");
let languageRequested = false;
const listeners = new Set<Listener>();

const getSnapshot = (): Strings => currentStrings;

export const getCurrentStrings = (): Strings => currentStrings;

const requestLanguage = (): void => {
  if (languageRequested)
    return;
  languageRequested = true;
  void window.SteamClient.Settings.GetCurrentLanguage()
    .then((language) => {
      currentStrings = getStrings(language);
      listeners.forEach((listener) => listener());
    })
    .catch((error) => {
      console.warn("[4deus Mod] Failed to read Steam language", error);
    });
};

const subscribe = (listener: Listener): (() => void) => {
  listeners.add(listener);
  requestLanguage();
  return () => listeners.delete(listener);
};

export const useStrings = (): Strings => useSyncExternalStore(
  subscribe,
  getSnapshot,
  getSnapshot,
);

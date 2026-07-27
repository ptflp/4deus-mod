import { useEffect, useState } from "react";

const translations = {
  english: {
    keyboard: "Keyboard",
    enabled: "Enable keyboard module",
    enabledDescription: "Enable keyboard fixes and customization",
    keepOnTop: "Keep keyboard on top",
    keepOnTopDescription: "Bring the Steam keyboard overlay above application windows",
    labels: "Secondary key labels",
    labelsDescription: "Show letters from another enabled Steam layout",
    secondaryLayout: "Secondary layout",
    secondaryLayoutDescription: "Automatic follows an enabled layout that is not currently active",
    automatic: "Automatic",
  },
  russian: {
    keyboard: "Клавиатура",
    enabled: "Включить модуль клавиатуры",
    enabledDescription: "Исправления и настройки виртуальной клавиатуры",
    keepOnTop: "Клавиатура поверх окон",
    keepOnTopDescription: "Выводить оверлей клавиатуры поверх окон приложений",
    labels: "Вторые подписи клавиш",
    labelsDescription: "Показывать буквы из другой включённой раскладки Steam",
    secondaryLayout: "Вторая раскладка",
    secondaryLayoutDescription: "Автоматически выбирается включённая раскладка, которая сейчас не активна",
    automatic: "Автоматически",
  },
};

export type Strings = typeof translations.english;

export const useStrings = (): Strings => {
  const [language, setLanguage] = useState<keyof typeof translations>("english");

  useEffect(() => {
    window.SteamClient.Settings.GetCurrentLanguage()
      .then((value) => setLanguage(value === "russian" ? "russian" : "english"))
      .catch((error) => console.warn("[4deus Mod] Failed to read Steam language", error));
  }, []);

  return translations[language];
};

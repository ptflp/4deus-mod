import type { WindowInstance } from "./modules/keyboard/types";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      [elementName: string]: unknown;
    }
  }

  interface Window {
    SP_REACT: typeof import("react");
    LocalizationManager?: {
      m_mapTokens?: Map<string, string>;
    };
    SteamUIStore: {
      ActiveWindowInstance?: WindowInstance;
    };
  }
}

export {};

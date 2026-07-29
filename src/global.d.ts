import type { Attributes } from "react";

import type { WindowInstance } from "./modules/keyboard/types";

declare global {
  namespace JSX {
    interface IntrinsicAttributes extends Attributes {}

    interface IntrinsicElements {
      [elementName: string]: unknown;
    }
  }

  interface Window {
    appStore: {
      GetAppOverviewByAppID(appId: number): {
        appid: number;
        app_type: number;
        display_name: string;
      } | undefined;
      allApps: Array<{
        appid: number;
        app_type: number;
        display_name: string;
      }>;
    };
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

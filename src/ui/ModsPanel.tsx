import {
  DialogButton,
  Field,
  Navigation,
  PanelSection,
  PanelSectionRow,
  Tabs,
  Toggle,
} from "@decky/ui";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import {
  FaCubes,
  FaCog,
  FaDesktop,
  FaGamepad,
  FaKeyboard,
  FaPlus,
  FaProjectDiagram,
} from "react-icons/fa";

import { useStrings, type Strings } from "../core/localization";
import {
  type ModuleId,
  type ModuleRegistry,
  type ModuleSnapshot,
} from "../core/moduleRegistry";
import type { SettingsStore } from "../core/settings";
import {
  AppBridgePopularPanel,
} from "../modules/appBridge/AppBridgePopularPanel";
import type { AppBridgeApi } from "../modules/appBridge/types";
import { ControllerPanel } from "../modules/controller/ControllerPanel";
import type { ControllerApi } from "../modules/controller/types";
import {
  KeyboardQuickPanel,
} from "../modules/keyboard/KeyboardPanel";
import {
  MangoHudPanel,
} from "../modules/nestedDesktop/MangoHudPanel";
import {
  NestedDesktopRuntimePanel,
} from "../modules/nestedDesktop/NestedDesktopRuntimePanel";
import type {
  MangoHudApi,
  NestedDesktopApi,
} from "../modules/nestedDesktop/types";
import {
  APP_BRIDGE_SETTINGS_ROUTE,
  CONTROLLER_SETTINGS_ROUTE,
  KEYBOARD_SETTINGS_ROUTE,
  NESTED_DESKTOP_SETTINGS_ROUTE,
} from "./routes";

interface ModsPanelProps {
  appBridgeApi: AppBridgeApi;
  controllerApi: ControllerApi;
  mangoHudApi: MangoHudApi;
  modules: ModuleRegistry;
  nestedDesktopApi: NestedDesktopApi;
  settings: SettingsStore;
}

interface ModuleDefinition {
  description: string;
  icon: React.ReactNode;
  id: ModuleId;
  route: string;
  title: string;
}

const MODS_PANEL_CSS = `
  .fourdeus-mod-tabs > div > div:first-child::before {
    background: #0d141c;
    box-shadow: none;
    backdrop-filter: none;
  }

  .fourdeus-mod-tabs [role="tabpanel"] {
    box-sizing: border-box;
    padding-bottom: 56px !important;
    padding-left: 8px !important;
    padding-right: 8px !important;
    scroll-padding-bottom: 56px;
  }
`;

const MODS_PANEL_STYLE = {
  height: "95%",
  marginTop: "-12px",
  maxHeight: "calc(100vh - 112px)",
  overflow: "hidden",
  position: "fixed",
  width: "300px",
} as const;

const openSettings = (route: string): void => {
  Navigation.Navigate(route);
  Navigation.CloseSideMenus();
};

const definitions = (strings: Strings): ModuleDefinition[] => [
  {
    description: strings.enabledDescription,
    icon: <FaKeyboard />,
    id: "keyboard",
    route: KEYBOARD_SETTINGS_ROUTE,
    title: strings.keyboard,
  },
  {
    description: strings.trackpadAutoRecoveryDescription,
    icon: <FaGamepad />,
    id: "controller",
    route: CONTROLLER_SETTINGS_ROUTE,
    title: strings.controller,
  },
  {
    description: strings.nestedDesktopHotkeysDescription,
    icon: <FaDesktop />,
    id: "nestedDesktop",
    route: NESTED_DESKTOP_SETTINGS_ROUTE,
    title: "Nested Desktop",
  },
  {
    description: strings.appBridgeEnabledDescription,
    icon: <FaProjectDiagram />,
    id: "appBridge",
    route: APP_BRIDGE_SETTINGS_ROUTE,
    title: strings.appBridge,
  },
];

interface ModuleFieldProps {
  definition: ModuleDefinition;
  modules: ModuleRegistry;
  snapshot: ModuleSnapshot;
}

const ModuleField = ({
  definition,
  modules,
  snapshot,
}: ModuleFieldProps) => {
  const state = snapshot[definition.id];
  return (
    <Field
      label={definition.title}
      description={state.error ?? definition.description}
      icon={definition.icon}
      childrenLayout="inline"
      childrenContainerWidth="max"
      inlineWrap="keep-inline"
      verticalAlignment="center"
    >
      <Toggle
        disabled={state.busy || !state.available}
        value={state.enabled}
        onChange={(enabled) =>
          void modules.setEnabled(definition.id, enabled)}
      />
    </Field>
  );
};

interface SettingsLinkProps {
  icon?: React.ReactNode;
  label: string;
  route: string;
  title: string;
}

const SettingsLink = ({
  icon,
  label,
  route,
  title,
}: SettingsLinkProps) => (
  <PanelSection title={title}>
    <PanelSectionRow>
      <DialogButton
        aria-label={`${title}: ${label}`}
        onClick={() => openSettings(route)}
        style={{ width: "100%" }}
      >
        <span
          style={{
            alignItems: "center",
            display: "flex",
            gap: "8px",
            justifyContent: "center",
          }}
        >
          {icon ?? <FaCog />}
          <span>{label}</span>
        </span>
      </DialogButton>
    </PanelSectionRow>
  </PanelSection>
);

interface ModuleTabProps {
  appBridgeApi: AppBridgeApi;
  controllerApi: ControllerApi;
  definition: ModuleDefinition;
  mangoHudApi: MangoHudApi;
  nestedDesktopApi: NestedDesktopApi;
  settings: SettingsStore;
  settingsLabel: string;
}

const ModuleTab = ({
  appBridgeApi,
  controllerApi,
  definition,
  mangoHudApi,
  nestedDesktopApi,
  settings,
  settingsLabel,
}: ModuleTabProps) => (
  <>
    <SettingsLink
      icon={definition.id === "appBridge" ? <FaPlus /> : undefined}
      label={definition.id === "appBridge" ? "Add App" : settingsLabel}
      route={definition.route}
      title={definition.title}
    />
    {definition.id === "keyboard" && (
      <KeyboardQuickPanel settings={settings} />
    )}
    {definition.id === "controller" && (
      <ControllerPanel api={controllerApi} />
    )}
    {definition.id === "nestedDesktop" && (
      <>
        <NestedDesktopRuntimePanel
          api={nestedDesktopApi}
          showBindings
        />
        <MangoHudPanel api={mangoHudApi} />
      </>
    )}
    {definition.id === "appBridge" && (
      <AppBridgePopularPanel
        api={appBridgeApi}
        settings={settings}
      />
    )}
  </>
);

export const ModsPanel = ({
  appBridgeApi,
  controllerApi,
  mangoHudApi,
  modules,
  nestedDesktopApi,
  settings,
}: ModsPanelProps) => {
  const strings = useStrings();
  const snapshot = useSyncExternalStore(
    modules.subscribe,
    modules.getSnapshot,
  );
  const moduleDefinitions = useMemo(
    () => definitions(strings),
    [strings],
  );
  const settingsLabel = useMemo(
    () => window.LocalizationManager?.m_mapTokens?.get("Settings")
      ?? strings.pluginSettings,
    [strings],
  );
  const enabledDefinitions = useMemo(
    () => moduleDefinitions.filter(({ id }) => snapshot[id].enabled),
    [moduleDefinitions, snapshot],
  );
  const visibleTabs = useMemo(
    () => ["modules", ...enabledDefinitions.map(({ id }) => id)],
    [enabledDefinitions],
  );
  const [activeTab, setActiveTab] = useState("modules");

  useEffect(() => {
    if (!visibleTabs.includes(activeTab))
      setActiveTab("modules");
  }, [activeTab, visibleTabs]);

  const handleShowTab = useCallback(
    (tab: string) => setActiveTab(
      visibleTabs.includes(tab) ? tab : "modules",
    ),
    [visibleTabs],
  );
  const moduleList = useMemo(
    () => (
      <PanelSection title="4deus Mod">
        {moduleDefinitions.map((definition) => (
          <ModuleField
            key={definition.id}
            definition={definition}
            modules={modules}
            snapshot={snapshot}
          />
        ))}
      </PanelSection>
    ),
    [moduleDefinitions, modules, snapshot],
  );
  const tabs = useMemo(
    () => [
      {
        id: "modules",
        title: <FaCubes />,
        content: moduleList,
      },
      ...enabledDefinitions.map((definition) => ({
        id: definition.id,
        title: definition.icon,
        content: (
          <ModuleTab
            appBridgeApi={appBridgeApi}
            controllerApi={controllerApi}
            definition={definition}
            mangoHudApi={mangoHudApi}
            nestedDesktopApi={nestedDesktopApi}
            settings={settings}
            settingsLabel={settingsLabel}
          />
        ),
      })),
    ],
    [
      appBridgeApi,
      controllerApi,
      enabledDefinitions,
      mangoHudApi,
      moduleList,
      nestedDesktopApi,
      settings,
      settingsLabel,
    ],
  );

  return (
    <>
      <style>{MODS_PANEL_CSS}</style>
      <div
        className="fourdeus-mod-tabs"
        style={MODS_PANEL_STYLE}
      >
        <Tabs
          activeTab={activeTab}
          onShowTab={handleShowTab}
          tabs={tabs}
        />
      </div>
    </>
  );
};

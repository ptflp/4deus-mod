import {
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { useStrings } from "../../core/localization";
import {
  AUTO_LAYOUT,
  type LanguageSwitchShortcut,
  type ModSettings,
  type SettingsStore,
} from "../../core/settings";
import { AdvancedSettings } from "../../ui/AdvancedSettings";
import {
  getEnabledLayouts,
  getLayoutDisplayName,
  type SteamKeyboardLayout,
} from "./steamLayouts";

interface KeyboardPanelProps {
  settings: SettingsStore;
}

interface KeyboardBehaviorRowsProps {
  keyboard: ModSettings["keyboard"];
  settings: SettingsStore;
  strings: ReturnType<typeof useStrings>;
}

const KeyboardBehaviorRows = ({
  keyboard,
  settings,
  strings,
}: KeyboardBehaviorRowsProps) => (
  <>
    <PanelSectionRow>
      <ToggleField
        label={strings.keepOnTop}
        description={strings.keepOnTopDescription}
        checked={keyboard.keepOnTop}
        onChange={(keepOnTop) => settings.updateKeyboard({ keepOnTop })}
      />
    </PanelSectionRow>
    <PanelSectionRow>
      <ToggleField
        label={strings.keepOpenAfterEnter}
        description={strings.keepOpenAfterEnterDescription}
        checked={keyboard.keepOpenAfterEnter}
        onChange={(keepOpenAfterEnter) => settings.updateKeyboard({
          keepOpenAfterEnter,
        })}
      />
    </PanelSectionRow>
    <PanelSectionRow>
      <ToggleField
        label={strings.systemKeyLayer}
        description={strings.systemKeyLayerDescription}
        checked={keyboard.systemKeyLayer}
        onChange={(systemKeyLayer) => settings.updateKeyboard({
          systemKeyLayer,
        })}
      />
    </PanelSectionRow>
    <PanelSectionRow>
      <ToggleField
        label={strings.holdHints}
        description={strings.holdHintsDescription}
        checked={keyboard.holdHints}
        onChange={(holdHints) => settings.updateKeyboard({ holdHints })}
      />
    </PanelSectionRow>
  </>
);

export const KeyboardQuickPanel = ({
  settings,
}: KeyboardPanelProps) => {
  const strings = useStrings();
  const keyboard = useSyncExternalStore(
    settings.subscribe,
    settings.getKeyboardSnapshot,
  );

  return (
    <PanelSection title={strings.keyboard}>
      <KeyboardBehaviorRows
        keyboard={keyboard}
        settings={settings}
        strings={strings}
      />
    </PanelSection>
  );
};

const layoutSignature = (layouts: SteamKeyboardLayout[]): string =>
  layouts.map((layout) => `${layout.layout}:${layout.name}`).join(",");

export const KeyboardPanel = ({ settings }: KeyboardPanelProps) => {
  const strings = useStrings();
  const keyboard = useSyncExternalStore(
    settings.subscribe,
    settings.getKeyboardSnapshot,
  );
  const [layouts, setLayouts] = useState(getEnabledLayouts);
  const currentLayoutSignature = useRef(layoutSignature(layouts));

  useEffect(() => {
    const timer = window.setInterval(() => {
      const nextLayouts = getEnabledLayouts();
      const nextSignature = layoutSignature(nextLayouts);
      if (nextSignature === currentLayoutSignature.current)
        return;
      currentLayoutSignature.current = nextSignature;
      setLayouts(nextLayouts);
    }, 1500);
    return () => window.clearInterval(timer);
  }, []);

  const layoutOptions = useMemo(
    () => [
      {
        data: AUTO_LAYOUT,
        label: strings.automatic,
      },
      ...layouts.map((layout) => ({
        data: layout.layout.toString(),
        label: getLayoutDisplayName(layout),
      })),
    ],
    [layouts, strings.automatic],
  );

  const selectedLayout = layoutOptions.some(
    (option) => option.data === keyboard.secondaryLayout,
  )
    ? keyboard.secondaryLayout
    : AUTO_LAYOUT;
  return (
    <>
      <PanelSection title={strings.keyboard}>
        <KeyboardBehaviorRows
          keyboard={keyboard}
          settings={settings}
          strings={strings}
        />
      </PanelSection>
      <PanelSection title={strings.languageSwitchShortcut}>
      <PanelSectionRow>
        <ToggleField
          label={strings.languageSwitchShortcut}
          description={strings.languageSwitchShortcutDescription}
          checked={keyboard.languageSwitchShortcutEnabled}
          onChange={(languageSwitchShortcutEnabled) => settings.updateKeyboard({
            languageSwitchShortcutEnabled,
          })}
        />
      </PanelSectionRow>
      {keyboard.languageSwitchShortcutEnabled && (
        <PanelSectionRow>
          <DropdownItem
            label={strings.languageSwitchShortcutChoice}
            menuLabel={strings.languageSwitchShortcutChoice}
            rgOptions={[
              { data: "alt-shift", label: "Alt + Shift" },
              { data: "ctrl-shift", label: "Ctrl + Shift" },
              { data: "meta-space", label: "Cmd + Space" },
              { data: "native", label: "★ Steam" },
            ]}
            selectedOption={keyboard.languageSwitchShortcut}
            onChange={({ data }) => settings.updateKeyboard({
              languageSwitchShortcut: (
                data.toString() as LanguageSwitchShortcut
              ),
            })}
          />
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <ToggleField
          label={strings.labels}
          description={strings.labelsDescription}
          checked={keyboard.secondaryLabels}
          onChange={(secondaryLabels) => settings.updateKeyboard({
            secondaryLabels,
            secondaryLayerSwapped: secondaryLabels
              && keyboard.secondaryLayerSwapped,
          })}
        />
      </PanelSectionRow>
      {keyboard.secondaryLabels && (
        <>
          <PanelSectionRow>
            <DropdownItem
              label={strings.secondaryLayout}
              description={strings.secondaryLayoutDescription}
              menuLabel={strings.secondaryLayout}
              rgOptions={layoutOptions}
              selectedOption={selectedLayout}
              onChange={({ data }) => settings.updateKeyboard({
                secondaryLayout: data.toString(),
              })}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ToggleField
              label={strings.secondaryLabelsQwertyOnly}
              description={strings.secondaryLabelsQwertyOnlyDescription}
              checked={keyboard.secondaryLabelsQwertyOnly}
              onChange={(secondaryLabelsQwertyOnly) =>
                settings.updateKeyboard({ secondaryLabelsQwertyOnly })}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ToggleField
              label={strings.autoSwapVisualLayer}
              description={strings.autoSwapVisualLayerDescription}
              checked={keyboard.autoSwapVisualLayer}
              onChange={(autoSwapVisualLayer) => settings.updateKeyboard({
                autoSwapVisualLayer,
              })}
            />
          </PanelSectionRow>
        </>
      )}
      </PanelSection>
      <AdvancedSettings
        label={strings.advancedSettings}
        description={strings.advancedSettingsDescription}
        moduleId="keyboard"
        settings={settings}
      >
        <PanelSection title={strings.diagnostics}>
          <PanelSectionRow>
            <ToggleField
              label={strings.diagnostics}
              description={strings.diagnosticsDescription}
              checked={keyboard.diagnostics}
              onChange={(diagnostics) =>
                settings.updateKeyboard({ diagnostics })}
            />
          </PanelSectionRow>
        </PanelSection>
      </AdvancedSettings>
    </>
  );
};

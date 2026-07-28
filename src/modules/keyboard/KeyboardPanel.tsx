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
  type DeckButtonAction,
  type LanguageSwitchShortcut,
  type SettingsStore,
} from "../../core/settings";
import {
  DECK_BUTTONS,
} from "./deckButtonBindings";
import { QuickActionEditor } from "./QuickActionEditor";
import {
  getEnabledLayouts,
  getLayoutDisplayName,
  type SteamKeyboardLayout,
} from "./steamLayouts";

interface KeyboardPanelProps {
  settings: SettingsStore;
}

const layoutSignature = (layouts: SteamKeyboardLayout[]): string =>
  layouts.map((layout) => `${layout.layout}:${layout.name}`).join(",");

const deckButtonActionOptions: Array<{
  data: DeckButtonAction;
  label: string;
}> = [
  { data: "none", label: "—" },
  { data: "KEY_ESC", label: "Esc" },
  { data: "KEY_SPACE", label: "Space" },
  { data: "KEY_BACKSPACE", label: "Backspace" },
  { data: "KEY_ENTER", label: "Enter" },
  { data: "KEY_TAB", label: "Tab" },
  { data: "KEY_LEFTCTRL", label: "Ctrl" },
  { data: "KEY_LEFTALT", label: "Alt" },
  { data: "KEY_LEFTSHIFT", label: "Shift" },
];

export const KeyboardPanel = ({ settings }: KeyboardPanelProps) => {
  const strings = useStrings();
  const snapshot = useSyncExternalStore(
    settings.subscribe,
    settings.getSnapshot,
  );
  const keyboard = snapshot.keyboard;
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

  const deckButtonBindingRow = (
    button: (typeof DECK_BUTTONS)[number],
  ) => {
    if (
      keyboard.deckButtonQuickActionsEnabled
      && keyboard.deckButtonSecondLayerEnabled
      && button.button === "r4"
    ) {
      return null;
    }
    return (
    <>
      <PanelSectionRow>
        <DropdownItem
          label={`${button.label} — ${strings.keyBinding}`}
          menuLabel={button.label}
          rgOptions={deckButtonActionOptions}
          selectedOption={keyboard.deckButtonBindings[button.button]}
          onChange={({ data }) => settings.updateKeyboard({
            deckButtonBindings: {
              ...keyboard.deckButtonBindings,
              [button.button]: data.toString() as DeckButtonAction,
            },
          })}
        />
      </PanelSectionRow>
      {keyboard.deckButtonQuickActionsEnabled && (
        <QuickActionEditor
          actions={keyboard.deckButtonQuickActions}
          button={button.button}
          buttonLabel={button.label}
          setNumber={1}
          strings={strings}
          onChange={(deckButtonQuickActions) => settings.updateKeyboard({
            deckButtonQuickActions,
          })}
        />
      )}
      {keyboard.deckButtonQuickActionsEnabled
        && keyboard.deckButtonSecondLayerEnabled
        && button.button !== "r4" && (
        <QuickActionEditor
          actions={keyboard.deckButtonSecondLayerActions}
          button={button.button}
          buttonLabel={button.label}
          setNumber={2}
          strings={strings}
          onChange={(deckButtonSecondLayerActions) => settings.updateKeyboard({
            deckButtonSecondLayerActions,
          })}
        />
      )}
    </>
    );
  };

  return (
    <PanelSection title={strings.keyboard}>
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
              { data: "native", label: "Steam (Default)" },
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
          label={strings.deckButtonBindings}
          description={strings.deckButtonBindingsDescription}
          checked={keyboard.deckButtonBindingsEnabled}
          onChange={(deckButtonBindingsEnabled) => settings.updateKeyboard({
            deckButtonBindingsEnabled,
          })}
        />
      </PanelSectionRow>
      {keyboard.deckButtonBindingsEnabled && (
        <>
          <PanelSectionRow>
            <ToggleField
              label={strings.quickAction}
              description={strings.quickActionsDescription}
              checked={keyboard.deckButtonQuickActionsEnabled}
              onChange={(deckButtonQuickActionsEnabled) =>
                settings.updateKeyboard({ deckButtonQuickActionsEnabled })}
            />
          </PanelSectionRow>
          {keyboard.deckButtonQuickActionsEnabled && (
            <PanelSectionRow>
              <ToggleField
                label={strings.secondHotkeyLayer}
                description={strings.secondHotkeyLayerDescription}
                checked={keyboard.deckButtonSecondLayerEnabled}
                onChange={(deckButtonSecondLayerEnabled) =>
                  settings.updateKeyboard({ deckButtonSecondLayerEnabled })}
              />
            </PanelSectionRow>
          )}
          {deckButtonBindingRow(DECK_BUTTONS[0])}
          {deckButtonBindingRow(DECK_BUTTONS[1])}
          {deckButtonBindingRow(DECK_BUTTONS[2])}
          {deckButtonBindingRow(DECK_BUTTONS[3])}
          {deckButtonBindingRow(DECK_BUTTONS[4])}
          {deckButtonBindingRow(DECK_BUTTONS[5])}
          {deckButtonBindingRow(DECK_BUTTONS[6])}
        </>
      )}
      <PanelSectionRow>
        <ToggleField
          label={strings.labels}
          description={strings.labelsDescription}
          checked={keyboard.secondaryLabels}
          onChange={(secondaryLabels) => settings.updateKeyboard({
            secondaryLabels,
          })}
        />
      </PanelSectionRow>
      {keyboard.secondaryLabels && (
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
      )}
      <PanelSectionRow>
        <ToggleField
          label={strings.diagnostics}
          description={strings.diagnosticsDescription}
          checked={keyboard.diagnostics}
          onChange={(diagnostics) => settings.updateKeyboard({ diagnostics })}
        />
      </PanelSectionRow>
    </PanelSection>
  );
};

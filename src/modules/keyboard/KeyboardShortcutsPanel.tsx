import {
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import {
  Fragment,
  useMemo,
  useSyncExternalStore,
} from "react";

import { useStrings } from "../../core/localization";
import type {
  DeckButtonAction,
  SettingsStore,
} from "../../core/settings";
import { DECK_BUTTONS } from "./deckButtonBindings";
import { QuickActionEditor } from "./QuickActionEditor";

interface KeyboardShortcutsPanelProps {
  settings: SettingsStore;
}

export const KeyboardShortcutsPanel = ({
  settings,
}: KeyboardShortcutsPanelProps) => {
  const strings = useStrings();
  const keyboard = useSyncExternalStore(
    settings.subscribe,
    settings.getKeyboardSnapshot,
  );
  const deckButtonActionOptions = useMemo<Array<{
    data: DeckButtonAction;
    label: string;
  }>>(() => [
    { data: "none", label: "—" },
    { data: "KEY_ESC", label: "Esc" },
    { data: "KEY_SPACE", label: strings.keySpace },
    { data: "KEY_BACKSPACE", label: strings.keyBackspace },
    { data: "KEY_ENTER", label: "Enter" },
    { data: "KEY_TAB", label: "Tab" },
    { data: "KEY_LEFTCTRL", label: "Ctrl" },
    { data: "KEY_LEFTALT", label: "Alt" },
    { data: "KEY_LEFTSHIFT", label: "Shift" },
  ], [strings]);
  const r4IsSecondLayerModifier = keyboard.deckButtonQuickActionsEnabled
    && keyboard.deckButtonSecondLayerEnabled;
  const configurableButtons = r4IsSecondLayerModifier
    ? DECK_BUTTONS.filter(({ button }) => button !== "r4")
    : DECK_BUTTONS;

  return (
    <>
      <PanelSection title={strings.hotkeys}>
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
        {keyboard.deckButtonBindingsEnabled
          && configurableButtons.map((button) => (
            <Fragment key={button.button}>
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
            </Fragment>
          ))}
      </PanelSection>
      <PanelSection title={strings.quickActions}>
        <PanelSectionRow>
          <ToggleField
            label={strings.quickAction}
            description={strings.quickActionsDescription}
            checked={keyboard.deckButtonQuickActionsEnabled}
            disabled={!keyboard.deckButtonBindingsEnabled}
            onChange={(deckButtonQuickActionsEnabled) =>
              settings.updateKeyboard({ deckButtonQuickActionsEnabled })}
          />
        </PanelSectionRow>
        {keyboard.deckButtonBindingsEnabled
          && keyboard.deckButtonQuickActionsEnabled && (
          <>
            <PanelSectionRow>
              <ToggleField
                label={strings.secondHotkeyLayer}
                description={strings.secondHotkeyLayerDescription}
                checked={keyboard.deckButtonSecondLayerEnabled}
                onChange={(deckButtonSecondLayerEnabled) =>
                  settings.updateKeyboard({ deckButtonSecondLayerEnabled })}
              />
            </PanelSectionRow>
            {configurableButtons.map((button) => (
              <Fragment key={`primary-${button.button}`}>
                <QuickActionEditor
                  actions={keyboard.deckButtonQuickActions}
                  button={button.button}
                  buttonLabel={button.label}
                  setNumber={1}
                  strings={strings}
                  onChange={(deckButtonQuickActions) =>
                    settings.updateKeyboard({ deckButtonQuickActions })}
                />
              </Fragment>
            ))}
            {keyboard.deckButtonSecondLayerEnabled
              && configurableButtons.map((button) => (
                <Fragment key={`secondary-${button.button}`}>
                  <QuickActionEditor
                    actions={keyboard.deckButtonSecondLayerActions}
                    button={button.button}
                    buttonLabel={button.label}
                    setNumber={2}
                    strings={strings}
                    onChange={(deckButtonSecondLayerActions) =>
                      settings.updateKeyboard({ deckButtonSecondLayerActions })}
                  />
                </Fragment>
              ))}
          </>
        )}
      </PanelSection>
    </>
  );
};

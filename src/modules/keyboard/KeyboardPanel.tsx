import {
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { useStrings } from "../../core/localization";
import { AUTO_LAYOUT, type SettingsStore } from "../../core/settings";
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

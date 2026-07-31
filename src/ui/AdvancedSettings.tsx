import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import {
  type ReactNode,
  useSyncExternalStore,
} from "react";

import type {
  AdvancedModule,
  SettingsStore,
} from "../core/settings";

interface AdvancedSettingsProps {
  children?: ReactNode;
  description: string;
  label: string;
  moduleId: AdvancedModule;
  settings: SettingsStore;
}

export const AdvancedSettings = ({
  children,
  description,
  label,
  moduleId,
  settings,
}: AdvancedSettingsProps) => {
  const advancedModules = useSyncExternalStore(
    settings.subscribe,
    settings.getAdvancedModulesSnapshot,
  );
  const enabled = advancedModules[moduleId];

  return (
    <>
      <PanelSection title={label}>
        <PanelSectionRow>
          <ToggleField
            label={label}
            description={description}
            checked={enabled}
            onChange={(nextEnabled) =>
              settings.updateAdvancedModule(moduleId, nextEnabled)}
          />
        </PanelSectionRow>
      </PanelSection>
      {enabled && children}
    </>
  );
};

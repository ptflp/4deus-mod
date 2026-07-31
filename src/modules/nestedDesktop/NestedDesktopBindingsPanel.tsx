import {
  DialogButton,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import {
  Fragment,
  useEffect,
  useState,
} from "react";

import { useStrings } from "../../core/localization";
import {
  NESTED_DESKTOP_ACTION_OPTIONS,
  NESTED_DESKTOP_BINDING_GROUPS,
  type NestedDesktopBindingAction,
  type NestedDesktopBindingSource,
} from "./nestedDesktopBindings";
import type {
  NestedDesktopApi,
  NestedDesktopMouseStatus,
} from "./types";

interface NestedDesktopBindingsPanelProps {
  api: NestedDesktopApi;
}

export const NestedDesktopBindingsPanel = ({
  api,
}: NestedDesktopBindingsPanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<NestedDesktopMouseStatus>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getNestedDesktopMouseStatus()
      .then(setStatus)
      .catch((error) => setMessage(
        error instanceof Error ? error.message : String(error),
      ));
  }, []);

  const run = async (
    action: () => Promise<NestedDesktopMouseStatus>,
    successMessage = "",
  ): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      const nextStatus = await action();
      setStatus(nextStatus);
      setMessage(nextStatus.error ?? successMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const setBinding = (
    source: NestedDesktopBindingSource,
    action: NestedDesktopBindingAction,
  ): void => {
    void run(() => api.setNestedDesktopBinding(source, action));
  };

  return (
    <>
      <PanelSection title={strings.nestedDesktopHotkeys}>
        <PanelSectionRow>
          <div>{strings.nestedDesktopHotkeysDescription}</div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.nestedDesktopHotkeysEnabled}
            description={strings.nestedDesktopHotkeysEnabledDescription}
            checked={status?.bindingsEnabled ?? true}
            disabled={busy || !status?.available}
            onChange={(enabled) =>
              void run(() => api.setNestedDesktopBindingsEnabled(enabled))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={busy || !status?.available}
            onClick={() => void run(
              api.resetNestedDesktopBindings,
              strings.nestedDesktopHotkeysReset,
            )}
            style={{ width: "100%" }}
          >
            {strings.resetNestedDesktopHotkeys}
          </DialogButton>
        </PanelSectionRow>
        {message && (
          <PanelSectionRow>
            <div>{message}</div>
          </PanelSectionRow>
        )}
      </PanelSection>

      {status?.bindingsEnabled
        && NESTED_DESKTOP_BINDING_GROUPS.map((group) => (
          <PanelSection key={group.title} title={group.title}>
            {group.sources.map(({ source, label }) => (
              <Fragment key={source}>
                <PanelSectionRow>
                  <DropdownItem
                    label={label}
                    menuLabel={strings.keyBinding}
                    rgOptions={NESTED_DESKTOP_ACTION_OPTIONS}
                    selectedOption={status.bindings[source] ?? "none"}
                    disabled={busy}
                    onChange={({ data }) =>
                      setBinding(source, data.toString())}
                  />
                </PanelSectionRow>
              </Fragment>
            ))}
          </PanelSection>
        ))}
    </>
  );
};

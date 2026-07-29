import {
  DropdownItem,
  PanelSectionRow,
} from "@decky/ui";
import { Fragment } from "react";

import type { Strings } from "../../core/translations";
import type {
  DeckButton,
  DeckQuickActions,
} from "../../core/settings";
import {
  DECK_QUICK_KEY_GROUPS,
  parseDeckQuickChord,
} from "./deckButtonBindings";

interface QuickActionEditorProps {
  actions: DeckQuickActions;
  button: DeckButton;
  buttonLabel: string;
  onChange: (actions: DeckQuickActions) => void;
  setNumber: 1 | 2;
  strings: Strings;
}

const SLOT_OPTIONS = [
  { data: "", label: "—" },
  {
    label: "Ctrl / Alt / Shift",
    options: [
      { data: "Ctrl", label: "Ctrl" },
      { data: "Alt", label: "Alt" },
      { data: "Shift", label: "Shift" },
    ],
  },
  ...DECK_QUICK_KEY_GROUPS.map((group) => ({
    label: group.label,
    options: group.options.map((option) => ({
      data: option.token ?? option.label,
      label: option.label,
    })),
  })),
];

const MAX_CHORD_KEYS = 4;

const chordTokens = (value: string): string[] =>
  value.split("+").map((token) => token.trim()).filter(Boolean)
    .slice(0, MAX_CHORD_KEYS);

const normalizeChord = (tokens: string[]): string => {
  const raw = tokens.filter(Boolean).join("+");
  const chord = parseDeckQuickChord(raw);
  return chord
    ? chord.label.split(" + ").join("+")
    : raw;
};

export const QuickActionEditor = ({
  actions,
  button,
  buttonLabel,
  onChange,
  setNumber,
  strings,
}: QuickActionEditorProps) => {
  const value = actions[button];
  const tokens = chordTokens(value);
  const chord = parseDeckQuickChord(value);
  const title = `${buttonLabel} — ${strings.quickAction} ${setNumber}`;
  const description = chord?.label
    ?? (value.trim() ? strings.invalidQuickAction : strings.quickActionHint);

  const updateSlot = (index: number, data: unknown): void => {
    const nextTokens = [...tokens];
    nextTokens[index] = data?.toString() ?? "";
    const nextValue = normalizeChord(nextTokens);
    onChange({
      ...actions,
      [button]: nextValue,
    });
  };

  return (
    <>
      {Array.from({ length: MAX_CHORD_KEYS }, (_, index) => {
        if (index > 0 && !tokens[index - 1])
          return null;
        return (
          <Fragment key={index}>
            <PanelSectionRow>
              <DropdownItem
                label={index === 0 ? title : `${title} — ${index + 1}`}
                description={index === 0 ? description : undefined}
                menuLabel={strings.keyBinding}
                rgOptions={SLOT_OPTIONS}
                selectedOption={tokens[index] ?? ""}
                onChange={({ data }) => updateSlot(index, data)}
              />
            </PanelSectionRow>
          </Fragment>
        );
      })}
    </>
  );
};

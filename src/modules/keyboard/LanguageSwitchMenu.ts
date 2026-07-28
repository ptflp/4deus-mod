import type { LanguageSwitchShortcut } from "../../core/settings";
import {
  findKey,
  LANGUAGE_SWITCH_OPTIONS,
  resolveLanguageSwitchOption,
} from "./systemKeys";

const OPTION_KEY_CLASS = "fourdeus-language-switch-option";
const SELECTED_KEY_CLASS = "fourdeus-language-switch-option-selected";
const LABEL_CLASS = "fourdeus-language-switch-option-label";
const STYLE_ID = "fourdeus-language-switch-menu-style";

const STYLES = `
  .${OPTION_KEY_CLASS} {
    position: relative !important;
  }

  .${OPTION_KEY_CLASS} > :not(.${LABEL_CLASS}) span:not(.${LABEL_CLASS}),
  .${OPTION_KEY_CLASS} > :not(.${LABEL_CLASS}) svg,
  .${OPTION_KEY_CLASS} .fourdeus-secondary-label {
    visibility: hidden !important;
  }

  .${LABEL_CLASS} {
    position: absolute;
    inset: 0;
    z-index: 6;
    display: flex;
    align-items: center;
    justify-content: center;
    color: inherit;
    font-size: 0.72em;
    font-weight: 600;
    line-height: 0.95;
    text-align: center;
    white-space: pre-line;
    pointer-events: none;
  }

  .${SELECTED_KEY_CLASS} > :first-child {
    outline: 2px solid #1a9fff;
    outline-offset: -2px;
    background: rgba(26, 159, 255, 0.3) !important;
  }
`;

export class LanguageSwitchMenu {
  private keyboard?: HTMLElement;
  private onSelect?: (shortcut: LanguageSwitchShortcut) => void;
  private visible = false;

  bind(keyboard: HTMLElement): void {
    this.unbind();
    this.keyboard = keyboard;
  }

  unbind(): void {
    this.hide();
    this.keyboard?.ownerDocument.getElementById(STYLE_ID)?.remove();
    this.keyboard = undefined;
  }

  show(
    selected: LanguageSwitchShortcut,
    onSelect: (shortcut: LanguageSwitchShortcut) => void,
  ): void {
    const keyboard = this.keyboard;
    if (!keyboard)
      return;

    this.hide();
    this.ensureStyles();
    this.onSelect = onSelect;
    this.visible = true;

    for (const option of LANGUAGE_SWITCH_OPTIONS) {
      const key = findKey(keyboard, option.row, option.column);
      if (!key)
        continue;
      key.classList.add(OPTION_KEY_CLASS);
      key.classList.toggle(SELECTED_KEY_CLASS, option.value === selected);
      const nativeKey = key.firstElementChild as HTMLElement | null;
      const label = key.ownerDocument.createElement("span");
      label.className = LABEL_CLASS;
      label.textContent = option.label;
      label.setAttribute("aria-hidden", "true");
      (nativeKey ?? key).appendChild(label);
    }
  }

  hide(): void {
    this.keyboard
      ?.querySelectorAll<HTMLElement>(`.${OPTION_KEY_CLASS}`)
      .forEach((key) => {
        key.classList.remove(OPTION_KEY_CLASS, SELECTED_KEY_CLASS);
        key.querySelectorAll<HTMLElement>(`.${LABEL_CLASS}`)
          .forEach((label) => label.remove());
      });
    this.onSelect = undefined;
    this.visible = false;
  }

  isVisible(): boolean {
    return this.visible;
  }

  isOptionKey(key: HTMLElement): boolean {
    return this.visible && resolveLanguageSwitchOption(key) !== undefined;
  }

  selectKey(key: HTMLElement): boolean {
    if (!this.visible)
      return false;
    const option = resolveLanguageSwitchOption(key);
    if (!option)
      return false;
    const onSelect = this.onSelect;
    this.hide();
    onSelect?.(option.value);
    return true;
  }

  private ensureStyles(): void {
    const document = this.keyboard?.ownerDocument;
    if (!document || document.getElementById(STYLE_ID))
      return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = STYLES;
    document.head.appendChild(style);
  }
}

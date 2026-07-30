import type { LanguageSwitchShortcut } from "../../core/settings";
import {
  findKey,
  LANGUAGE_SWITCH_OPTIONS,
  resolveLanguageSwitchOption,
  type LanguageSwitchMenuValue,
} from "./systemKeys";

const OPTION_KEY_CLASS = "fourdeus-language-switch-option";
const SELECTED_KEY_CLASS = "fourdeus-language-switch-option-selected";
const LABEL_CLASS = "fourdeus-language-switch-option-label";
const STYLE_ID = "fourdeus-language-switch-menu-style";

const STYLES = `
  .${OPTION_KEY_CLASS} {
    position: relative !important;
  }

  .${OPTION_KEY_CLASS} > :first-child > :not(.${LABEL_CLASS}),
  .${OPTION_KEY_CLASS} > .fourdeus-deck-binding-label,
  .${OPTION_KEY_CLASS} > .fourdeus-hold-hint-label {
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
  private onSelect?: (value: LanguageSwitchMenuValue) => void;
  private observer?: MutationObserver;
  private refreshFrame?: number;
  private selected: LanguageSwitchShortcut = "native";
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
    onSelect: (value: LanguageSwitchMenuValue) => void,
  ): void {
    const keyboard = this.keyboard;
    if (!keyboard)
      return;

    this.hide();
    this.ensureStyles();
    this.onSelect = onSelect;
    this.selected = selected;
    this.visible = true;
    this.renderOptions();

    const MutationObserverConstructor =
      keyboard.ownerDocument.defaultView?.MutationObserver
      ?? MutationObserver;
    this.observer = new MutationObserverConstructor(() =>
      this.scheduleRefresh());
    this.observer.observe(keyboard, {
      childList: true,
      subtree: true,
    });
  }

  hide(): void {
    this.observer?.disconnect();
    this.observer = undefined;
    const ownerWindow = this.keyboard?.ownerDocument.defaultView;
    if (this.refreshFrame !== undefined)
      ownerWindow?.cancelAnimationFrame(this.refreshFrame);
    this.refreshFrame = undefined;
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

  private scheduleRefresh(): void {
    const ownerWindow = this.keyboard?.ownerDocument.defaultView;
    if (!this.visible || !ownerWindow || this.refreshFrame !== undefined)
      return;
    this.refreshFrame = ownerWindow.requestAnimationFrame(() => {
      this.refreshFrame = undefined;
      this.renderOptions();
    });
  }

  private renderOptions(): void {
    const keyboard = this.keyboard;
    if (!keyboard || !this.visible)
      return;

    const optionKeys = new Set<HTMLElement>();
    for (const option of LANGUAGE_SWITCH_OPTIONS) {
      const key = findKey(keyboard, option.row, option.column);
      if (!key)
        continue;
      optionKeys.add(key);
      this.renderOption(key, option);
    }

    this.clearStaleOptionKeys(keyboard, optionKeys);
  }

  private renderOption(
    key: HTMLElement,
    option: (typeof LANGUAGE_SWITCH_OPTIONS)[number],
  ): void {
    key.classList.add(OPTION_KEY_CLASS);
    key.classList.toggle(
      SELECTED_KEY_CLASS,
      option.value === this.selected,
    );
    const label = this.ensureOptionLabel(key);
    if (label.textContent !== option.label)
      label.textContent = option.label;
  }

  private ensureOptionLabel(key: HTMLElement): HTMLElement {
    const parent = (key.firstElementChild as HTMLElement | null) ?? key;
    const labels = Array.from(
      key.querySelectorAll<HTMLElement>(`.${LABEL_CLASS}`),
    );
    const label = labels.shift()
      ?? key.ownerDocument.createElement("span");
    labels.forEach((duplicate) => duplicate.remove());
    label.className = LABEL_CLASS;
    label.setAttribute("aria-hidden", "true");
    if (label.parentElement !== parent)
      parent.appendChild(label);
    return label;
  }

  private clearStaleOptionKeys(
    keyboard: HTMLElement,
    optionKeys: Set<HTMLElement>,
  ): void {
    keyboard
      .querySelectorAll<HTMLElement>(`.${OPTION_KEY_CLASS}`)
      .forEach((key) => {
        if (optionKeys.has(key))
          return;
        key.classList.remove(OPTION_KEY_CLASS, SELECTED_KEY_CLASS);
        key.querySelectorAll<HTMLElement>(`.${LABEL_CLASS}`)
          .forEach((label) => label.remove());
      });
  }
}

import type { LanguageSwitchShortcut } from "../../core/settings";

const MENU_ID = "fourdeus-language-switch-menu";
const STYLE_ID = "fourdeus-language-switch-menu-style";

const OPTIONS: ReadonlyArray<{
  label: string;
  value: LanguageSwitchShortcut;
}> = [
  { label: "Alt + Shift", value: "alt-shift" },
  { label: "Ctrl + Shift", value: "ctrl-shift" },
  { label: "Cmd + Space", value: "meta-space" },
  { label: "Steam (default)", value: "native" },
];

const STYLES = `
  #${MENU_ID} {
    position: fixed;
    left: 50%;
    bottom: 18%;
    z-index: 10000;
    display: grid;
    grid-template-columns: repeat(2, minmax(170px, 1fr));
    gap: 10px;
    width: min(520px, calc(100vw - 32px));
    padding: 14px;
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 12px;
    background: rgba(24, 28, 35, 0.97);
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.55);
    transform: translateX(-50%);
  }

  #${MENU_ID} button {
    min-height: 54px;
    padding: 8px 12px;
    border: 2px solid transparent;
    border-radius: 8px;
    color: white;
    background: rgba(255, 255, 255, 0.1);
    font: inherit;
    font-size: 18px;
  }

  #${MENU_ID} button:hover,
  #${MENU_ID} button:focus {
    outline: none;
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.65);
  }

  #${MENU_ID} button[data-selected="true"] {
    border-color: #1a9fff;
    background: rgba(26, 159, 255, 0.28);
  }
`;

export class LanguageSwitchMenu {
  private document?: Document;
  private menu?: HTMLElement;

  bind(document: Document): void {
    this.unbind();
    this.document = document;
  }

  unbind(): void {
    this.hide();
    this.document?.getElementById(STYLE_ID)?.remove();
    this.document = undefined;
  }

  show(
    selected: LanguageSwitchShortcut,
    onSelect: (shortcut: LanguageSwitchShortcut) => void,
  ): void {
    const document = this.document;
    if (!document)
      return;
    this.hide();
    this.ensureStyles();

    const menu = document.createElement("div");
    menu.id = MENU_ID;
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", "Language switch shortcut");
    for (const option of OPTIONS) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = option.label;
      button.dataset.selected = (option.value === selected).toString();
      button.setAttribute("role", "menuitemradio");
      button.setAttribute(
        "aria-checked",
        (option.value === selected).toString(),
      );
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        onSelect(option.value);
        this.hide();
      });
      menu.appendChild(button);
    }
    document.body.appendChild(menu);
    this.menu = menu;
    menu.querySelector<HTMLElement>('[data-selected="true"]')?.focus();
  }

  hide(): void {
    this.menu?.remove();
    this.menu = undefined;
  }

  private ensureStyles(): void {
    const document = this.document;
    if (!document || document.getElementById(STYLE_ID))
      return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = STYLES;
    document.head.appendChild(style);
  }
}

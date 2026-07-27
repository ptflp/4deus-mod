import {
  EMOJI_KEY,
  findKey,
  findNamedKey,
  KEY_SELECTOR,
  LAYOUT_KEY,
  NATIVE_ALT_KEY,
  SYNTHETIC_ALT_KEY,
  SYNTHETIC_FUNCTION_KEY,
} from "./systemKeys";

const SYSTEM_KEY_CLASS = "fourdeus-system-key";
const ACTIVE_KEY_CLASS = "fourdeus-system-key-active";
export const PRESSED_KEY_CLASS = "fourdeus-system-key-pressed";
const LABEL_CLASS = "fourdeus-system-key-label";
const STYLE_ID = "fourdeus-system-key-style";

interface ViewState {
  altActive: boolean;
  controlActive: boolean;
  functionLayer: boolean;
  visible: boolean;
}

interface Presentation {
  active?: boolean;
  label: string;
}

const STYLES = `
  .${SYSTEM_KEY_CLASS} {
    position: relative !important;
  }

  .${SYSTEM_KEY_CLASS} > :not(.${LABEL_CLASS}) span:not(.${LABEL_CLASS}),
  .${SYSTEM_KEY_CLASS} > :not(.${LABEL_CLASS}) svg,
  .${SYSTEM_KEY_CLASS} .fourdeus-secondary-label {
    visibility: hidden !important;
  }

  .${LABEL_CLASS} {
    position: absolute;
    inset: 0;
    z-index: 4;
    display: flex;
    align-items: center;
    justify-content: center;
    color: inherit;
    pointer-events: none;
  }

  .${ACTIVE_KEY_CLASS} {
    outline: none !important;
  }

  .${PRESSED_KEY_CLASS} > :first-child {
    filter: brightness(0.62);
    transform: scale(0.97);
  }
`;

const readStyleRules = (sheet: CSSStyleSheet): CSSStyleRule[] => {
  try {
    return Array.from(sheet.cssRules) as CSSStyleRule[];
  } catch {
    return [];
  }
};

const activeToggleClass = (rule: CSSStyleRule): string | undefined => {
  const background = rule.style?.getPropertyValue("background-color");
  return background?.includes("--key-toggleon-background-color")
    ? rule.selectorText?.match(/^\.([A-Za-z0-9_-]+)$/)?.[1]
    : undefined;
};

export class SystemKeyView {
  private keyboard?: HTMLElement;
  private toggleOnClass?: string;

  bind(keyboard: HTMLElement): void {
    this.unbind();
    this.keyboard = keyboard;
  }

  unbind(): void {
    this.clear();
    this.keyboard = undefined;
    this.toggleOnClass = undefined;
  }

  render(state: ViewState): void {
    const keyboard = this.keyboard;
    if (!keyboard)
      return;

    this.ensureStyles();
    const altKey = state.visible ? this.ensureAltKey(keyboard) : null;
    const functionKey = state.visible ? this.ensureFunctionKey(keyboard) : null;
    if (!state.visible)
      findNamedKey(keyboard, SYNTHETIC_ALT_KEY)?.remove();
    if (!state.visible)
      findNamedKey(keyboard, SYNTHETIC_FUNCTION_KEY)?.remove();
    const presentations = state.visible
      ? this.buildPresentations(keyboard, altKey, functionKey, state)
      : new Map<HTMLElement, Presentation>();

    keyboard.querySelectorAll<HTMLElement>(`.${SYSTEM_KEY_CLASS}`).forEach(
      (key) => {
        if (!presentations.has(key))
          this.clearKey(key);
      },
    );
    presentations.forEach((presentation, key) =>
      this.renderKey(key, presentation),
    );
  }

  private buildPresentations(
    keyboard: HTMLElement,
    altKey: HTMLElement | null,
    functionKey: HTMLElement | null,
    state: ViewState,
  ): Map<HTMLElement, Presentation> {
    const entries: Array<[HTMLElement | null, Presentation]> = [
      [
        findNamedKey(keyboard, EMOJI_KEY),
        { label: "Ctrl", active: state.controlActive },
      ],
      [
        functionKey,
        { label: "Fn", active: state.functionLayer },
      ],
      [findKey(keyboard, 0, 0), { label: "Esc" }],
      [altKey, { label: "Alt", active: state.altActive }],
    ];
    if (state.functionLayer) {
      entries.push([findKey(keyboard, 0, 13), { label: "Delete" }]);
      for (let column = 1; column <= 12; column += 1)
        entries.push([findKey(keyboard, 0, column), { label: `F${column}` }]);
    }
    return new Map(
      entries.filter(
        (entry): entry is [HTMLElement, Presentation] => entry[0] !== null,
      ),
    );
  }

  private renderKey(key: HTMLElement, presentation: Presentation): void {
    const active = Boolean(presentation.active);
    key.classList.add(SYSTEM_KEY_CLASS);
    key.classList.toggle(ACTIVE_KEY_CLASS, active);

    const toggleOnClass = this.resolveToggleOnClass();
    if (toggleOnClass)
      key.firstElementChild?.classList.toggle(toggleOnClass, active);

    const nativeKey = key.firstElementChild as HTMLElement | null;
    let label = nativeKey?.querySelector<HTMLElement>(
      `:scope > .${LABEL_CLASS}`,
    ) ?? key.querySelector<HTMLElement>(`:scope > .${LABEL_CLASS}`);
    if (!label) {
      label = key.ownerDocument.createElement("span");
      label.className = LABEL_CLASS;
      label.setAttribute("aria-hidden", "true");
      (nativeKey ?? key).appendChild(label);
    } else if (nativeKey && label.parentElement !== nativeKey) {
      nativeKey.appendChild(label);
    }
    this.syncTypography(label, key);
    if (label.textContent !== presentation.label)
      label.textContent = presentation.label;
  }

  private clear(): void {
    this.keyboard
      ?.querySelectorAll<HTMLElement>(`.${SYSTEM_KEY_CLASS}`)
      .forEach((key) => this.clearKey(key));
    this.keyboard?.ownerDocument.getElementById(STYLE_ID)?.remove();
    this.keyboard
      ?.querySelectorAll<HTMLElement>(
        `${KEY_SELECTOR}[data-key="${SYNTHETIC_ALT_KEY}"], `
        + `${KEY_SELECTOR}[data-key="${SYNTHETIC_FUNCTION_KEY}"]`,
      )
      .forEach((key) => key.remove());
  }

  private ensureFunctionKey(keyboard: HTMLElement): HTMLElement | null {
    const existing = findNamedKey(keyboard, SYNTHETIC_FUNCTION_KEY);
    if (existing)
      return existing;

    const layout = findNamedKey(keyboard, LAYOUT_KEY);
    if (!layout?.parentElement)
      return null;
    const functionKey = layout.cloneNode(true) as HTMLElement;
    functionKey.dataset.key = SYNTHETIC_FUNCTION_KEY;
    functionKey.dataset.keyCol = "fn";
    functionKey.querySelectorAll<HTMLElement>("[data-key]").forEach((element) => {
      element.dataset.key = SYNTHETIC_FUNCTION_KEY;
      element.dataset.keyCol = "fn";
    });
    layout.parentElement.insertBefore(functionKey, layout.nextSibling);
    return functionKey;
  }

  private ensureAltKey(keyboard: HTMLElement): HTMLElement | null {
    const native = findNamedKey(keyboard, NATIVE_ALT_KEY);
    if (native)
      return native;

    const existing = findNamedKey(keyboard, SYNTHETIC_ALT_KEY);
    if (existing)
      return existing;

    const arrow = findNamedKey(keyboard, "ArrowLeft");
    if (!arrow?.parentElement)
      return null;
    const alt = arrow.cloneNode(true) as HTMLElement;
    alt.dataset.key = SYNTHETIC_ALT_KEY;
    alt.dataset.keyCol = "alt";
    alt.querySelectorAll<HTMLElement>("[data-key]").forEach((element) => {
      element.dataset.key = SYNTHETIC_ALT_KEY;
      element.dataset.keyCol = "alt";
    });
    arrow.parentElement.insertBefore(alt, arrow);
    return alt;
  }

  private clearKey(key: HTMLElement): void {
    key.classList.remove(
      SYSTEM_KEY_CLASS,
      ACTIVE_KEY_CLASS,
      PRESSED_KEY_CLASS,
    );
    if (this.toggleOnClass)
      key.firstElementChild?.classList.remove(this.toggleOnClass);
    key.querySelector(`.${LABEL_CLASS}`)?.remove();
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

  private resolveToggleOnClass(): string | undefined {
    if (this.toggleOnClass)
      return this.toggleOnClass;

    const document = this.keyboard?.ownerDocument;
    if (!document)
      return undefined;
    // Steam hashes class names, but its active-toggle class uses this stable
    // theme variable in every keyboard theme.
    this.toggleOnClass = Array.from(document.styleSheets)
      .flatMap(readStyleRules)
      .map(activeToggleClass)
      .find((className) => className !== undefined);
    return this.toggleOnClass;
  }

  private syncTypography(label: HTMLElement, key: HTMLElement): void {
    const keyboard = this.keyboard;
    const ownerWindow = keyboard?.ownerDocument.defaultView;
    if (!keyboard || !ownerWindow)
      return;
    const nativeLabel = key.querySelector<HTMLElement>(
      `:scope > :first-child span:not(.${LABEL_CLASS})`,
    ) ?? findKey(keyboard, 1, 1)?.querySelector<HTMLElement>(
      ":scope > :first-child span",
    );
    if (!nativeLabel)
      return;

    const style = ownerWindow.getComputedStyle(nativeLabel);
    Object.assign(label.style, {
      fontFamily: style.fontFamily,
      fontSize: style.fontSize,
      fontWeight: "400",
      letterSpacing: style.letterSpacing,
      lineHeight: style.lineHeight,
    });
  }
}

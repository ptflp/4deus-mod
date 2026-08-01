import {
  EMOJI_KEY,
  findKey,
  findNamedKey,
  LAYOUT_KEY,
} from "./systemKeys";

const HINT_KEY_CLASS = "fourdeus-hold-hint-key";
export const HOLD_HINT_LABEL_CLASS = "fourdeus-hold-hint-label";
const HINT_BADGE_CLASS = "fourdeus-hold-hint-badge";
const STYLE_ID = "fourdeus-hold-hint-style";

const STYLES = `
  .${HINT_KEY_CLASS} {
    position: relative !important;
  }

  .${HOLD_HINT_LABEL_CLASS} {
    position: absolute;
    top: 7%;
    left: 5%;
    z-index: 8;
    display: flex;
    align-items: center;
    pointer-events: none;
  }

  .${HINT_BADGE_CLASS} {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.08em 0.3em;
    border: 1px solid currentColor;
    border-radius: 0.35em;
    background: rgba(0, 0, 0, 0.28);
    color: inherit;
    line-height: 1;
  }
`;

export class HoldHintView {
  private keyboard?: HTMLElement;
  private lastSignature?: string;

  bind(keyboard: HTMLElement): void {
    this.unbind();
    this.keyboard = keyboard;
  }

  unbind(): void {
    this.clear();
    this.keyboard = undefined;
  }

  render(
    enabled: boolean,
    systemMode: boolean,
    functionLayer: boolean,
    languageSwitchEnabled: boolean,
    label: string,
  ): void {
    const keyboard = this.keyboard;
    if (!keyboard)
      return;
    const targets = this.resolveTargets(
      keyboard,
      enabled,
      systemMode,
      functionLayer,
      languageSwitchEnabled,
    );
    const signature = [
      enabled,
      systemMode,
      functionLayer,
      languageSwitchEnabled,
      label,
    ].join(":");
    if (
      signature === this.lastSignature
      && keyboard.querySelectorAll(`.${HOLD_HINT_LABEL_CLASS}`).length
        === targets.length
    ) {
      return;
    }

    this.clearLabels();
    this.lastSignature = signature;
    if (targets.length === 0)
      return;
    this.ensureStyles();
    targets.forEach((key) => this.renderHint(key, label));
  }

  private resolveTargets(
    keyboard: HTMLElement,
    enabled: boolean,
    systemMode: boolean,
    functionLayer: boolean,
    languageSwitchEnabled: boolean,
  ): HTMLElement[] {
    if (!enabled || !systemMode)
      return [];
    const targets = [
      findNamedKey(keyboard, EMOJI_KEY),
      findKey(keyboard, 3, 10),
    ];
    if (!functionLayer && languageSwitchEnabled)
      targets.push(findNamedKey(keyboard, LAYOUT_KEY));
    return targets.filter((key): key is HTMLElement => key !== null);
  }

  private renderHint(key: HTMLElement, label: string): void {
    key.classList.add(HINT_KEY_CLASS);
    const container = key.ownerDocument.createElement("span");
    container.className = HOLD_HINT_LABEL_CLASS;
    container.setAttribute("aria-hidden", "true");
    const badge = key.ownerDocument.createElement("span");
    badge.className = HINT_BADGE_CLASS;
    badge.textContent = label;
    container.appendChild(badge);
    key.appendChild(container);
    this.syncTypography(container, key);
  }

  private syncTypography(label: HTMLElement, key: HTMLElement): void {
    const ownerWindow = key.ownerDocument.defaultView;
    const nativeLabel = key.querySelector<HTMLElement>(
      ":scope > :first-child span",
    ) ?? findNamedKey(this.keyboard!, "q")
      ?.querySelector<HTMLElement>(":scope > :first-child span");
    if (!ownerWindow || !nativeLabel)
      return;

    const style = ownerWindow.getComputedStyle(nativeLabel);
    const nativeSize = Number.parseFloat(style.fontSize);
    Object.assign(label.style, {
      fontFamily: style.fontFamily,
      fontSize: `${Math.max(8, nativeSize * 0.42)}px`,
      fontWeight: "500",
    });
  }

  private clear(): void {
    this.clearLabels();
    this.lastSignature = undefined;
    this.keyboard?.ownerDocument.getElementById(STYLE_ID)?.remove();
  }

  private clearLabels(): void {
    this.keyboard
      ?.querySelectorAll<HTMLElement>(`.${HOLD_HINT_LABEL_CLASS}`)
      .forEach((label) => label.remove());
    this.keyboard
      ?.querySelectorAll<HTMLElement>(`.${HINT_KEY_CLASS}`)
      .forEach((key) => key.classList.remove(HINT_KEY_CLASS));
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

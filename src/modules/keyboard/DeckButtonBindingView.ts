import type {
  DeckButtonBindings,
  DeckQuickActions,
} from "../../core/settings";
import {
  DECK_BUTTONS,
  parseDeckQuickChord,
} from "./deckButtonBindings";
import {
  EMOJI_KEY,
  findKey,
  findKeyBySystemName,
  findNamedKey,
} from "./systemKeys";

const BINDING_KEY_CLASS = "fourdeus-deck-binding-key";
export const DECK_BINDING_LABEL_CLASS = "fourdeus-deck-binding-label";
const BINDING_BADGE_CLASS = "fourdeus-deck-binding-badge";
const LAYER_STATUS_CLASS = "fourdeus-deck-layer-status";
const STYLE_ID = "fourdeus-deck-binding-style";

const STYLES = `
  .${BINDING_KEY_CLASS} {
    position: relative !important;
  }

  .${DECK_BINDING_LABEL_CLASS} {
    position: absolute;
    right: 5%;
    bottom: 7%;
    z-index: 8;
    display: flex;
    gap: 3px;
    align-items: center;
    pointer-events: none;
  }

  .${LAYER_STATUS_CLASS} {
    right: auto;
    left: 5%;
  }

  .${BINDING_BADGE_CLASS} {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.6em;
    padding: 0.08em 0.28em;
    border: 1px solid currentColor;
    border-radius: 0.35em;
    background: rgba(0, 0, 0, 0.28);
    color: inherit;
    line-height: 1;
  }
`;

export class DeckButtonBindingView {
  private keyboard?: HTMLElement;
  private lastSignature?: string;

  bind(keyboard: HTMLElement): void {
    this.unbind();
    this.keyboard = keyboard;
  }

  unbind(): void {
    this.clear();
    this.keyboard = undefined;
    this.lastSignature = undefined;
  }

  render(
    enabled: boolean,
    bindings: DeckButtonBindings,
    quickActions: DeckQuickActions,
    secondLayerEnabled: boolean,
    secondLayerActive: boolean,
  ): void {
    const keyboard = this.keyboard;
    if (!keyboard)
      return;

    const targets = this.buildTargets(
      keyboard,
      enabled,
      bindings,
      quickActions,
      secondLayerEnabled,
    );
    const layerStatusKey = enabled && secondLayerEnabled
      ? findKey(keyboard, 4, 2) ?? undefined
      : undefined;
    const signature = JSON.stringify({
      enabled,
      labels: targets.map(({ key, labels }) => [
        key.dataset.keyRow,
        key.dataset.keyCol,
        labels,
      ]),
      secondLayerActive,
      secondLayerEnabled,
    });
    const expectedLabelCount = targets.length + (layerStatusKey ? 1 : 0);
    if (this.renderingIsCurrent(keyboard, signature, expectedLabelCount))
      return;

    this.clearLabels();
    this.lastSignature = signature;
    if (!enabled)
      return;
    this.ensureStyles();
    targets.forEach(({ key, labels }) => this.renderLabels(key, labels));
    if (layerStatusKey)
      this.renderLayerStatus(layerStatusKey, secondLayerActive);
  }

  private buildTargets(
    keyboard: HTMLElement,
    enabled: boolean,
    bindings: DeckButtonBindings,
    quickActions: DeckQuickActions,
    secondLayerEnabled: boolean,
  ): Array<{ key: HTMLElement; labels: string[] }> {
    const labelsByAction = new Map<string, string[]>();
    if (enabled) {
      DECK_BUTTONS.forEach(({ button, label }) => {
        if (secondLayerEnabled && button === "r4")
          return;
        const chord = parseDeckQuickChord(quickActions[button]);
        if (chord)
          return;
        const action = bindings[button];
        if (action === "none")
          return;
        const labels = labelsByAction.get(action) ?? [];
        labels.push(label);
        labelsByAction.set(action, labels);
      });
    }
    const targets: Array<{ key: HTMLElement; labels: string[] }> = [];
    labelsByAction.forEach((labels, action) => {
      const key = action === "KEY_LEFTCTRL"
        ? findNamedKey(keyboard, EMOJI_KEY)
        : findKeyBySystemName(keyboard, action);
      if (key)
        targets.push({ key, labels });
    });
    return targets;
  }

  private renderingIsCurrent(
    keyboard: HTMLElement,
    signature: string,
    expectedLabelCount: number,
  ): boolean {
    const renderedLabelCount = keyboard.querySelectorAll(
      `.${DECK_BINDING_LABEL_CLASS}`,
    ).length;
    return signature === this.lastSignature
      && renderedLabelCount === expectedLabelCount;
  }

  private renderLayerStatus(key: HTMLElement, active: boolean): void {
    key.classList.add(BINDING_KEY_CLASS);
    const container = key.ownerDocument.createElement("span");
    container.className = `${DECK_BINDING_LABEL_CLASS} ${LAYER_STATUS_CLASS}`;
    container.setAttribute("aria-hidden", "true");
    const badge = key.ownerDocument.createElement("span");
    badge.className = BINDING_BADGE_CLASS;
    badge.textContent = `SET ${active ? "2" : "1"}`;
    container.appendChild(badge);
    key.appendChild(container);
    this.syncTypography(container, key);
  }

  private renderLabels(key: HTMLElement, labels: string[]): void {
    key.classList.add(BINDING_KEY_CLASS);
    const container = key.ownerDocument.createElement("span");
    container.className = DECK_BINDING_LABEL_CLASS;
    container.setAttribute("aria-hidden", "true");
    labels.forEach((text) => {
      const badge = key.ownerDocument.createElement("span");
      badge.className = BINDING_BADGE_CLASS;
      badge.textContent = text;
      container.appendChild(badge);
    });
    key.appendChild(container);
    this.syncTypography(container, key);
  }

  private syncTypography(label: HTMLElement, key: HTMLElement): void {
    const ownerWindow = key.ownerDocument.defaultView;
    const nativeLabel = key.querySelector<HTMLElement>(
      ":scope > :first-child span",
    );
    if (!ownerWindow || !nativeLabel)
      return;

    const style = ownerWindow.getComputedStyle(nativeLabel);
    const nativeSize = Number.parseFloat(style.fontSize);
    Object.assign(label.style, {
      fontFamily: style.fontFamily,
      fontSize: `${Math.max(9, nativeSize * 0.48)}px`,
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
      ?.querySelectorAll<HTMLElement>(`.${DECK_BINDING_LABEL_CLASS}`)
      .forEach((label) => label.remove());
    this.keyboard
      ?.querySelectorAll<HTMLElement>(`.${BINDING_KEY_CLASS}`)
      .forEach((key) => key.classList.remove(BINDING_KEY_CLASS));
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

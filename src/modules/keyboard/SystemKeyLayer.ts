import type { NativeKeyboardInput } from "./types";

const LONG_PRESS_MS = 550;
const STEAM_KEY_LEFT_CONTROL = 103;
const HID_ESCAPE = 41;
const HID_F1 = 58;

const EMOJI_KEY = "SwitchKeys_Steam";
const LAYOUT_KEY = "SwitchKeys_Layout";
const KEY_SELECTOR = "[data-key-row][data-key-col]";
const SYSTEM_KEY_CLASS = "fourdeus-system-key";
const ACTIVE_KEY_CLASS = "fourdeus-system-key-active";
const LABEL_CLASS = "fourdeus-system-key-label";
const STYLE_ID = "fourdeus-system-key-style";

const HID_CODES_BY_POSITION: Record<string, number> = {
  "0:0": 53,
  "0:1": 30,
  "0:2": 31,
  "0:3": 32,
  "0:4": 33,
  "0:5": 34,
  "0:6": 35,
  "0:7": 36,
  "0:8": 37,
  "0:9": 38,
  "0:10": 39,
  "0:11": 45,
  "0:12": 46,
  "0:13": 42,
  "1:0": 43,
  "1:1": 20,
  "1:2": 26,
  "1:3": 8,
  "1:4": 21,
  "1:5": 23,
  "1:6": 28,
  "1:7": 24,
  "1:8": 12,
  "1:9": 18,
  "1:10": 19,
  "1:11": 47,
  "1:12": 48,
  "1:13": 49,
  "2:1": 4,
  "2:2": 22,
  "2:3": 7,
  "2:4": 9,
  "2:5": 10,
  "2:6": 11,
  "2:7": 13,
  "2:8": 14,
  "2:9": 15,
  "2:10": 51,
  "2:11": 52,
  "2:12": 40,
  "3:1": 29,
  "3:2": 27,
  "3:3": 6,
  "3:4": 25,
  "3:5": 5,
  "3:6": 17,
  "3:7": 16,
  "3:8": 54,
  "3:9": 55,
  "3:10": 56,
  "4:2": 44,
  "4:4": 80,
  "4:5": 79,
};

interface SystemKeyPresentation {
  active?: boolean;
  label: string;
}

const getPosition = (key: HTMLElement): string =>
  `${key.dataset.keyRow}:${key.dataset.keyCol}`;

const consume = (event: Event): void => {
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
};

export class SystemKeyLayer {
  private keyboard?: HTMLElement;
  private input?: NativeKeyboardInput;
  private enabled = false;
  private systemMode = false;
  private functionLayer = false;
  private controlActive = false;
  private holdTimer?: number;
  private heldKey?: HTMLElement;
  private heldInSystemMode = false;
  private longPressTriggered = false;
  private passThroughTouch?: HTMLElement;
  private suppressNextClick?: HTMLElement;

  bind(
    keyboard: HTMLElement,
    input: NativeKeyboardInput,
  ): void {
    this.unbind();
    this.keyboard = keyboard;
    this.input = input;
    const document = keyboard.ownerDocument;
    document.addEventListener("touchstart", this.onTouchStart, {
      capture: true,
      passive: false,
    });
    document.addEventListener("touchend", this.onTouchEnd, {
      capture: true,
      passive: false,
    });
    document.addEventListener("touchcancel", this.onTouchCancel, {
      capture: true,
      passive: false,
    });
    document.addEventListener("click", this.onClick, true);
    this.render();
  }

  unbind(): void {
    this.clearHold();
    this.releaseControl();
    if (this.keyboard) {
      const document = this.keyboard.ownerDocument;
      document.removeEventListener("touchstart", this.onTouchStart, true);
      document.removeEventListener("touchend", this.onTouchEnd, true);
      document.removeEventListener("touchcancel", this.onTouchCancel, true);
      document.removeEventListener("click", this.onClick, true);
      this.clearPresentation();
    }
    this.keyboard = undefined;
    this.input = undefined;
    this.systemMode = false;
    this.functionLayer = false;
    this.passThroughTouch = undefined;
    this.suppressNextClick = undefined;
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled)
      this.exitSystemMode();
    this.render();
  }

  refresh(): void {
    this.render();
  }

  private readonly onTouchStart = (event: TouchEvent): void => {
    if (!this.enabled)
      return;

    const key = this.getKey(event.target);
    if (!key || key === this.passThroughTouch)
      return;
    const isEmoji = key.dataset.key === EMOJI_KEY;
    if (!isEmoji && !this.isSystemKey(key))
      return;

    consume(event);
    this.clearHold();
    this.heldKey = key;
    this.heldInSystemMode = this.systemMode;
    if (isEmoji) {
      this.holdTimer = window.setTimeout(() => {
        this.holdTimer = undefined;
        this.longPressTriggered = true;
        if (this.systemMode)
          this.exitSystemMode();
        else
          this.enterSystemMode();
      }, LONG_PRESS_MS);
    }
  };

  private readonly onTouchEnd = (event: TouchEvent): void => {
    const key = this.heldKey;
    if (!key || key === this.passThroughTouch)
      return;

    consume(event);
    const wasLongPress = this.longPressTriggered;
    const startedInSystemMode = this.heldInSystemMode;
    this.clearHold();
    if (!wasLongPress) {
      if (key.dataset.key === EMOJI_KEY) {
        if (startedInSystemMode)
          this.toggleControl();
        else
          this.replayShortTouch(key, event);
      } else {
        this.activateSystemKey(key);
      }
    }
    this.suppressNextClick = key;
    window.setTimeout(() => {
      if (this.suppressNextClick === key)
        this.suppressNextClick = undefined;
    }, 0);
  };

  private readonly onTouchCancel = (event: TouchEvent): void => {
    if (!this.heldKey)
      return;
    consume(event);
    this.clearHold();
  };

  private readonly onClick = (event: MouseEvent): void => {
    const key = this.getKey(event.target);
    if (!key)
      return;

    if (key === this.suppressNextClick) {
      this.suppressNextClick = undefined;
      consume(event);
      return;
    }

    if (!this.enabled || !this.systemMode)
      return;

    if (key.dataset.key === EMOJI_KEY) {
      consume(event);
      this.toggleControl();
      return;
    }

    if (this.isSystemKey(key)) {
      consume(event);
      this.activateSystemKey(key);
    }
  };

  private getKey(target: EventTarget | null): HTMLElement | undefined {
    const candidate = target as Element | null;
    const element = typeof candidate?.closest === "function"
      ? candidate.closest<HTMLElement>(KEY_SELECTOR)
      : null;
    return element && this.keyboard?.contains(element) ? element : undefined;
  }

  private replayShortTouch(key: HTMLElement, source: TouchEvent): void {
    const ownerWindow = key.ownerDocument.defaultView;
    const TouchConstructor = ownerWindow?.Touch;
    const TouchEventConstructor = ownerWindow?.TouchEvent;
    const sourceTouch = source.changedTouches[0];
    if (!TouchConstructor || !TouchEventConstructor || !sourceTouch)
      return;

    const touch = new TouchConstructor({
      identifier: sourceTouch.identifier,
      target: key,
      clientX: sourceTouch.clientX,
      clientY: sourceTouch.clientY,
      screenX: sourceTouch.screenX,
      screenY: sourceTouch.screenY,
      pageX: sourceTouch.pageX,
      pageY: sourceTouch.pageY,
      radiusX: sourceTouch.radiusX,
      radiusY: sourceTouch.radiusY,
      rotationAngle: sourceTouch.rotationAngle,
      force: sourceTouch.force,
    });
    const options: TouchEventInit = {
      bubbles: true,
      cancelable: true,
      composed: true,
      changedTouches: [touch],
    };
    this.passThroughTouch = key;
    key.dispatchEvent(new TouchEventConstructor("touchstart", {
      ...options,
      touches: [touch],
      targetTouches: [touch],
    }));
    key.dispatchEvent(new TouchEventConstructor("touchend", {
      ...options,
      touches: [],
      targetTouches: [],
    }));
    this.passThroughTouch = undefined;
  }

  private enterSystemMode(): void {
    this.systemMode = true;
    this.functionLayer = false;
    this.render();
  }

  private exitSystemMode(): void {
    this.releaseControl();
    this.systemMode = false;
    this.functionLayer = false;
    this.render();
  }

  private toggleControl(): void {
    if (this.controlActive) {
      this.releaseControl();
      return;
    }
    if (!this.input?.ControllerKeyboardSetKeyState)
      return;
    this.input.ControllerKeyboardSetKeyState(STEAM_KEY_LEFT_CONTROL, true);
    this.controlActive = true;
    this.render();
  }

  private releaseControl(): void {
    if (this.controlActive)
      this.input?.ControllerKeyboardSetKeyState?.(STEAM_KEY_LEFT_CONTROL, false);
    this.controlActive = false;
    this.render();
  }

  private tapNativeKey(keyCode: number): void {
    const setKeyState = this.input?.ControllerKeyboardSetKeyState;
    if (!setKeyState)
      return;
    setKeyState(keyCode, true);
    setKeyState(keyCode, false);
    this.releaseControl();
  }

  private isSystemKey(key: HTMLElement): boolean {
    return this.systemMode && (
      key.dataset.key === LAYOUT_KEY
      || this.getSystemKeyCode(key) !== undefined
    );
  }

  private activateSystemKey(key: HTMLElement): void {
    if (!this.systemMode)
      return;
    if (key.dataset.key === LAYOUT_KEY) {
      this.functionLayer = !this.functionLayer;
      this.render();
      return;
    }
    const keyCode = this.getSystemKeyCode(key);
    if (keyCode !== undefined)
      this.tapNativeKey(keyCode);
  }

  private getSystemKeyCode(key: HTMLElement): number | undefined {
    const position = getPosition(key);
    if (position === "0:0")
      return HID_ESCAPE;
    const functionKey = this.getFunctionKey(position);
    if (functionKey !== undefined)
      return functionKey;
    return this.controlActive
      ? HID_CODES_BY_POSITION[position]
      : undefined;
  }

  private getFunctionKey(position: string): number | undefined {
    if (!this.functionLayer)
      return undefined;
    const column = Number(position.split(":")[1]);
    return position.startsWith("0:") && column >= 1 && column <= 12
      ? HID_F1 + column - 1
      : undefined;
  }

  private render(): void {
    const keyboard = this.keyboard;
    if (!keyboard)
      return;

    this.ensureStyles(keyboard.ownerDocument);
    const presentations = new Map<HTMLElement, SystemKeyPresentation>();
    if (this.enabled && this.systemMode) {
      const emoji = keyboard.querySelector<HTMLElement>(
        `${KEY_SELECTOR}[data-key="${EMOJI_KEY}"]`,
      );
      const layout = keyboard.querySelector<HTMLElement>(
        `${KEY_SELECTOR}[data-key="${LAYOUT_KEY}"]`,
      );
      const escape = keyboard.querySelector<HTMLElement>(
        `${KEY_SELECTOR}[data-key-row="0"][data-key-col="0"]`,
      );
      if (emoji)
        presentations.set(emoji, { label: "Ctrl", active: this.controlActive });
      if (layout)
        presentations.set(layout, { label: "Fn", active: this.functionLayer });
      if (escape)
        presentations.set(escape, { label: "Esc" });

      if (this.functionLayer) {
        for (let column = 1; column <= 12; column += 1) {
          const key = keyboard.querySelector<HTMLElement>(
            `${KEY_SELECTOR}[data-key-row="0"][data-key-col="${column}"]`,
          );
          if (key)
            presentations.set(key, { label: `F${column}` });
        }
      }
    }

    keyboard.querySelectorAll<HTMLElement>(`.${SYSTEM_KEY_CLASS}`).forEach(
      (key) => {
        if (!presentations.has(key))
          this.clearKeyPresentation(key);
      },
    );
    presentations.forEach((presentation, key) => {
      key.classList.add(SYSTEM_KEY_CLASS);
      key.classList.toggle(ACTIVE_KEY_CLASS, Boolean(presentation.active));
      let label = key.querySelector<HTMLElement>(`:scope > .${LABEL_CLASS}`);
      if (!label) {
        label = key.ownerDocument.createElement("span");
        label.className = LABEL_CLASS;
        label.setAttribute("aria-hidden", "true");
        key.appendChild(label);
      }
      if (label.textContent !== presentation.label)
        label.textContent = presentation.label;
    });
  }

  private clearPresentation(): void {
    this.keyboard
      ?.querySelectorAll<HTMLElement>(`.${SYSTEM_KEY_CLASS}`)
      .forEach((key) => this.clearKeyPresentation(key));
    this.keyboard?.ownerDocument.getElementById(STYLE_ID)?.remove();
  }

  private clearKeyPresentation(key: HTMLElement): void {
    key.classList.remove(SYSTEM_KEY_CLASS, ACTIVE_KEY_CLASS);
    key.querySelector(`:scope > .${LABEL_CLASS}`)?.remove();
  }

  private ensureStyles(document: Document): void {
    if (document.getElementById(STYLE_ID))
      return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .${SYSTEM_KEY_CLASS} {
        position: relative !important;
      }

      .${SYSTEM_KEY_CLASS} > :not(.${LABEL_CLASS}) span,
      .${SYSTEM_KEY_CLASS} > :not(.${LABEL_CLASS}) svg,
      .${SYSTEM_KEY_CLASS} > .fourdeus-secondary-label {
        visibility: hidden !important;
      }

      .${LABEL_CLASS} {
        position: absolute;
        inset: 0;
        z-index: 4;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-family: inherit;
        font-size: 18px;
        font-weight: 600;
        line-height: 1;
        pointer-events: none;
      }

      .${ACTIVE_KEY_CLASS} {
        outline: 2px solid #1a9fff;
        outline-offset: -3px;
      }
    `;
    document.head.appendChild(style);
  }

  private clearHold(): void {
    if (this.holdTimer !== undefined)
      window.clearTimeout(this.holdTimer);
    this.holdTimer = undefined;
    this.heldKey = undefined;
    this.heldInSystemMode = false;
    this.longPressTriggered = false;
  }
}

const LONG_PRESS_MS = 550;
const GAMEPAD_OK_BUTTON = 1;
const KEY_ESCAPE = "KEY_ESC";
const KEY_DELETE_FORWARD = "KEY_DELETE";

const EMOJI_KEY = "SwitchKeys_Steam";
const LAYOUT_KEY = "SwitchKeys_Layout";
const KEY_SELECTOR = "[data-key-row][data-key-col]";
const SYSTEM_KEY_CLASS = "fourdeus-system-key";
const ACTIVE_KEY_CLASS = "fourdeus-system-key-active";
const PRESSED_KEY_CLASS = "fourdeus-system-key-pressed";
const LABEL_CLASS = "fourdeus-system-key-label";
const STYLE_ID = "fourdeus-system-key-style";

const KEY_NAMES_BY_POSITION: Record<string, string> = {
  "0:0": "KEY_GRAVE",
  "0:1": "KEY_1",
  "0:2": "KEY_2",
  "0:3": "KEY_3",
  "0:4": "KEY_4",
  "0:5": "KEY_5",
  "0:6": "KEY_6",
  "0:7": "KEY_7",
  "0:8": "KEY_8",
  "0:9": "KEY_9",
  "0:10": "KEY_0",
  "0:11": "KEY_MINUS",
  "0:12": "KEY_EQUAL",
  "0:13": "KEY_BACKSPACE",
  "1:0": "KEY_TAB",
  "1:1": "KEY_Q",
  "1:2": "KEY_W",
  "1:3": "KEY_E",
  "1:4": "KEY_R",
  "1:5": "KEY_T",
  "1:6": "KEY_Y",
  "1:7": "KEY_U",
  "1:8": "KEY_I",
  "1:9": "KEY_O",
  "1:10": "KEY_P",
  "1:11": "KEY_LEFTBRACE",
  "1:12": "KEY_RIGHTBRACE",
  "1:13": "KEY_BACKSLASH",
  "2:1": "KEY_A",
  "2:2": "KEY_S",
  "2:3": "KEY_D",
  "2:4": "KEY_F",
  "2:5": "KEY_G",
  "2:6": "KEY_H",
  "2:7": "KEY_J",
  "2:8": "KEY_K",
  "2:9": "KEY_L",
  "2:10": "KEY_SEMICOLON",
  "2:11": "KEY_APOSTROPHE",
  "2:12": "KEY_ENTER",
  "3:1": "KEY_Z",
  "3:2": "KEY_X",
  "3:3": "KEY_C",
  "3:4": "KEY_V",
  "3:5": "KEY_B",
  "3:6": "KEY_N",
  "3:7": "KEY_M",
  "3:8": "KEY_COMMA",
  "3:9": "KEY_DOT",
  "3:10": "KEY_SLASH",
  "4:2": "KEY_SPACE",
  "4:4": "KEY_LEFT",
  "4:5": "KEY_RIGHT",
};

export type SystemKeySender = (
  keyName: string,
  withControl: boolean,
) => Promise<boolean>;

interface SystemKeyPresentation {
  active?: boolean;
  label: string;
}

interface GamepadButtonDetail {
  button: number;
  is_repeat?: boolean;
  [key: string]: unknown;
}

type HoldSource = "gamepad" | "touch";

const getPosition = (key: HTMLElement): string =>
  `${key.dataset.keyRow}:${key.dataset.keyCol}`;

const consume = (event: Event): void => {
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
};

export class SystemKeyLayer {
  private keyboard?: HTMLElement;
  private enabled = false;
  private defaultSystemMode = false;
  private systemMode = false;
  private functionLayer = false;
  private controlActive = false;
  private holdTimer?: number;
  private heldKey?: HTMLElement;
  private heldInSystemMode = false;
  private holdSource?: HoldSource;
  private gamepadButtonDetail?: GamepadButtonDetail;
  private longPressTriggered = false;
  private passThroughGamepad?: HTMLElement;
  private passThroughTouch?: HTMLElement;
  private suppressNextClick?: HTMLElement;
  private inputQueue = Promise.resolve();
  private toggleOnClass?: string;

  constructor(private readonly sendSystemKey: SystemKeySender) {}

  bind(keyboard: HTMLElement): void {
    this.unbind();
    this.keyboard = keyboard;
    if (this.enabled && this.defaultSystemMode) {
      this.systemMode = true;
      this.functionLayer = false;
    }
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
    document.addEventListener(
      "vgp_onbuttondown",
      this.onGamepadButtonDown as EventListener,
      true,
    );
    document.addEventListener(
      "vgp_onbuttonup",
      this.onGamepadButtonUp as EventListener,
      true,
    );
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
      document.removeEventListener(
        "vgp_onbuttondown",
        this.onGamepadButtonDown as EventListener,
        true,
      );
      document.removeEventListener(
        "vgp_onbuttonup",
        this.onGamepadButtonUp as EventListener,
        true,
      );
      document.removeEventListener("click", this.onClick, true);
      this.clearPresentation();
    }
    this.keyboard = undefined;
    this.systemMode = false;
    this.functionLayer = false;
    this.passThroughGamepad = undefined;
    this.passThroughTouch = undefined;
    this.suppressNextClick = undefined;
    this.toggleOnClass = undefined;
  }

  configure(enabled: boolean, defaultSystemMode: boolean): void {
    const wasEnabled = this.enabled;
    const previousDefault = this.defaultSystemMode;
    this.enabled = enabled;
    this.defaultSystemMode = defaultSystemMode;
    if (!enabled) {
      this.exitSystemMode();
    }
    else if (!wasEnabled || previousDefault !== defaultSystemMode) {
      if (defaultSystemMode)
        this.enterSystemMode();
      else
        this.exitSystemMode();
    }
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
    this.beginHold(key, "touch", isEmoji);
    if (!isEmoji)
      this.activateSystemKey(key);
  };

  private readonly onTouchEnd = (event: TouchEvent): void => {
    const key = this.heldKey;
    if (
      !key
      || this.holdSource !== "touch"
      || key === this.passThroughTouch
    )
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
      }
    }
    this.suppressNextClick = key;
    window.setTimeout(() => {
      if (this.suppressNextClick === key)
        this.suppressNextClick = undefined;
    }, 0);
  };

  private readonly onTouchCancel = (event: TouchEvent): void => {
    if (!this.heldKey || this.holdSource !== "touch")
      return;
    consume(event);
    this.clearHold();
  };

  private readonly onGamepadButtonDown = (event: Event): void => {
    const gamepadEvent = event as CustomEvent<GamepadButtonDetail>;
    if (!this.enabled || gamepadEvent.detail?.button !== GAMEPAD_OK_BUTTON)
      return;

    const key = this.getKey(event.target);
    if (!key || key === this.passThroughGamepad)
      return;
    const isEmoji = key.dataset.key === EMOJI_KEY;
    if (!isEmoji && !this.isSystemKey(key))
      return;

    consume(event);
    if (
      this.holdSource === "gamepad"
      && this.heldKey === key
      && gamepadEvent.detail.is_repeat
    ) {
      return;
    }
    this.beginHold(key, "gamepad", isEmoji);
    this.gamepadButtonDetail = { ...gamepadEvent.detail, is_repeat: false };
    if (!isEmoji)
      this.activateSystemKey(key);
  };

  private readonly onGamepadButtonUp = (event: Event): void => {
    const gamepadEvent = event as CustomEvent<GamepadButtonDetail>;
    const key = this.heldKey;
    if (
      gamepadEvent.detail?.button !== GAMEPAD_OK_BUTTON
      || !key
      || this.holdSource !== "gamepad"
      || key === this.passThroughGamepad
    ) {
      return;
    }

    consume(event);
    const wasLongPress = this.longPressTriggered;
    const startedInSystemMode = this.heldInSystemMode;
    const detail = this.gamepadButtonDetail ?? gamepadEvent.detail;
    this.clearHold();
    if (wasLongPress)
      return;

    if (key.dataset.key === EMOJI_KEY) {
      if (startedInSystemMode)
        this.toggleControl();
      else
        this.replayGamepadPress(key, detail);
    }
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

  private replayGamepadPress(
    key: HTMLElement,
    detail: GamepadButtonDetail,
  ): void {
    const CustomEventConstructor = key.ownerDocument.defaultView?.CustomEvent;
    if (!CustomEventConstructor)
      return;
    const options: CustomEventInit<GamepadButtonDetail> = {
      bubbles: true,
      cancelable: true,
      detail,
    };
    this.passThroughGamepad = key;
    key.dispatchEvent(new CustomEventConstructor("vgp_onbuttondown", options));
    key.dispatchEvent(new CustomEventConstructor("vgp_onbuttonup", options));
    this.passThroughGamepad = undefined;
  }

  private beginHold(
    key: HTMLElement,
    source: HoldSource,
    allowLongPress: boolean,
  ): void {
    this.clearHold();
    this.heldKey = key;
    key.classList.add(PRESSED_KEY_CLASS);
    this.heldInSystemMode = this.systemMode;
    this.holdSource = source;
    if (!allowLongPress)
      return;
    this.holdTimer = window.setTimeout(() => {
      this.holdTimer = undefined;
      this.longPressTriggered = true;
      if (this.systemMode)
        this.exitSystemMode();
      else
        this.enterSystemMode();
    }, LONG_PRESS_MS);
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
    this.controlActive = !this.controlActive;
    this.render();
  }

  private releaseControl(): void {
    this.controlActive = false;
    this.render();
  }

  private tapSystemKey(keyName: string): void {
    const withControl = this.controlActive;
    this.inputQueue = this.inputQueue
      .then(() => this.sendSystemKey(keyName, withControl))
      .then(() => undefined)
      .catch((error) => {
        console.error("[4deus Mod] Failed to send system key", error);
      });
    this.releaseControl();
  }

  private isSystemKey(key: HTMLElement): boolean {
    return this.systemMode && (
      key.dataset.key === LAYOUT_KEY
      || this.getSystemKeyName(key) !== undefined
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
    const keyName = this.getSystemKeyName(key);
    if (keyName !== undefined)
      this.tapSystemKey(keyName);
  }

  private getSystemKeyName(key: HTMLElement): string | undefined {
    const position = getPosition(key);
    if (position === "0:0")
      return KEY_ESCAPE;
    if (this.functionLayer && position === "0:13")
      return KEY_DELETE_FORWARD;
    const functionKey = this.getFunctionKey(position);
    if (functionKey !== undefined)
      return functionKey;
    return this.controlActive
      ? KEY_NAMES_BY_POSITION[position]
      : undefined;
  }

  private getFunctionKey(position: string): string | undefined {
    if (!this.functionLayer)
      return undefined;
    const column = Number(position.split(":")[1]);
    return position.startsWith("0:") && column >= 1 && column <= 12
      ? `KEY_F${column}`
      : undefined;
  }

  private render(): void {
    const keyboard = this.keyboard;
    if (!keyboard)
      return;

    this.ensureStyles(keyboard.ownerDocument);
    const toggleOnClass = this.resolveToggleOnClass(keyboard.ownerDocument);
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
      const deleteKey = keyboard.querySelector<HTMLElement>(
        `${KEY_SELECTOR}[data-key-row="0"][data-key-col="13"]`,
      );
      if (emoji)
        presentations.set(emoji, { label: "Ctrl", active: this.controlActive });
      if (layout)
        presentations.set(layout, { label: "Fn", active: this.functionLayer });
      if (escape)
        presentations.set(escape, { label: "Esc" });
      if (deleteKey && this.functionLayer)
        presentations.set(deleteKey, { label: "Delete" });

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
      if (toggleOnClass) {
        key.firstElementChild?.classList.toggle(
          toggleOnClass,
          Boolean(presentation.active),
        );
      }
      let label = key.querySelector<HTMLElement>(`:scope > .${LABEL_CLASS}`);
      if (!label) {
        label = key.ownerDocument.createElement("span");
        label.className = LABEL_CLASS;
        label.setAttribute("aria-hidden", "true");
        key.appendChild(label);
      }
      this.syncLabelTypography(label, key, keyboard);
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
    key.classList.remove(
      SYSTEM_KEY_CLASS,
      ACTIVE_KEY_CLASS,
      PRESSED_KEY_CLASS,
    );
    if (this.toggleOnClass)
      key.firstElementChild?.classList.remove(this.toggleOnClass);
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
    document.head.appendChild(style);
  }

  private resolveToggleOnClass(document: Document): string | undefined {
    if (this.toggleOnClass)
      return this.toggleOnClass;

    for (const sheet of Array.from(document.styleSheets)) {
      let rules: CSSRuleList;
      try {
        rules = sheet.cssRules;
      }
      catch {
        continue;
      }
      for (const rule of Array.from(rules)) {
        const styleRule = rule as CSSStyleRule;
        const background = styleRule.style?.getPropertyValue(
          "background-color",
        );
        if (!background?.includes("--key-toggleon-background-color"))
          continue;
        const match = styleRule.selectorText?.match(/^\.([A-Za-z0-9_-]+)$/);
        if (match) {
          this.toggleOnClass = match[1];
          return this.toggleOnClass;
        }
      }
    }
    return undefined;
  }

  private syncLabelTypography(
    label: HTMLElement,
    key: HTMLElement,
    keyboard: HTMLElement,
  ): void {
    const nativeLabel = key.querySelector<HTMLElement>(
      ":scope > :first-child span",
    ) ?? keyboard.querySelector<HTMLElement>(
      `${KEY_SELECTOR}[data-key-row="1"][data-key-col="1"]`
      + " > :first-child span",
    );
    const ownerWindow = keyboard.ownerDocument.defaultView;
    if (!nativeLabel || !ownerWindow)
      return;

    const style = ownerWindow.getComputedStyle(nativeLabel);
    label.style.fontFamily = style.fontFamily;
    label.style.fontSize = style.fontSize;
    label.style.fontWeight = "400";
    label.style.lineHeight = style.lineHeight;
    label.style.letterSpacing = style.letterSpacing;
  }

  private clearHold(): void {
    this.heldKey?.classList.remove(PRESSED_KEY_CLASS);
    if (this.holdTimer !== undefined)
      window.clearTimeout(this.holdTimer);
    this.holdTimer = undefined;
    this.heldKey = undefined;
    this.heldInSystemMode = false;
    this.holdSource = undefined;
    this.gamepadButtonDetail = undefined;
    this.longPressTriggered = false;
  }
}

import {
  EMOJI_KEY,
  isAltKey,
  KEY_SELECTOR,
  resolveSystemKey,
  SYNTHETIC_FUNCTION_KEY,
} from "./systemKeys";
import { PRESSED_KEY_CLASS, SystemKeyView } from "./SystemKeyView";

const LONG_PRESS_MS = 550;
const GAMEPAD_OK_BUTTON = 1;

export type SystemKeySender = (
  keyName: string,
  withControl: boolean,
  withAlt: boolean,
) => Promise<boolean>;

interface GamepadButtonDetail {
  button: number;
  is_repeat?: boolean;
  [key: string]: unknown;
}

type HoldSource = "gamepad" | "touch";

interface HoldState {
  gamepadDetail?: GamepadButtonDetail;
  key: HTMLElement;
  longPress: boolean;
  source: HoldSource;
  startedInSystemMode: boolean;
  timer?: number;
}

const consume = (event: Event): void => {
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
};

export class SystemKeyLayer {
  private readonly view = new SystemKeyView();
  private keyboard?: HTMLElement;
  private enabled = false;
  private defaultSystemMode = false;
  private systemMode = false;
  private functionLayer = false;
  private controlActive = false;
  private altActive = false;
  private hold?: HoldState;
  private listenerAbort?: AbortController;
  private passThroughKey?: HTMLElement;
  private suppressNextClick?: HTMLElement;
  private inputQueue = Promise.resolve();

  constructor(private readonly sendSystemKey: SystemKeySender) {}

  bind(keyboard: HTMLElement): void {
    this.unbind();
    this.keyboard = keyboard;
    if (this.enabled && this.defaultSystemMode) {
      this.systemMode = true;
      this.functionLayer = false;
    }
    this.view.bind(keyboard);
    const document = keyboard.ownerDocument;
    const AbortController =
      document.defaultView?.AbortController ?? window.AbortController;
    this.listenerAbort = new AbortController();
    const signal = this.listenerAbort.signal;
    document.addEventListener("touchstart", this.onTouchStart, {
      capture: true,
      passive: false,
      signal,
    });
    document.addEventListener("touchend", this.onTouchEnd, {
      capture: true,
      passive: false,
      signal,
    });
    document.addEventListener("touchcancel", this.onTouchCancel, {
      capture: true,
      passive: false,
      signal,
    });
    const capture = { capture: true, signal };
    document.addEventListener("vgp_onbuttondown", this.onGamepadButtonDown, capture);
    document.addEventListener("vgp_onbuttonup", this.onGamepadButtonUp, capture);
    document.addEventListener("click", this.onClick, capture);
    this.render();
  }

  unbind(): void {
    this.clearHold();
    this.controlActive = false;
    this.altActive = false;
    this.listenerAbort?.abort();
    this.listenerAbort = undefined;
    this.view.unbind();
    this.keyboard = undefined;
    this.systemMode = false;
    this.functionLayer = false;
    this.passThroughKey = undefined;
    this.suppressNextClick = undefined;
  }

  configure(enabled: boolean, defaultSystemMode: boolean): void {
    const resetMode = !enabled
      || !this.enabled
      || this.defaultSystemMode !== defaultSystemMode;
    this.enabled = enabled;
    this.defaultSystemMode = defaultSystemMode;
    if (resetMode)
      this.setSystemMode(enabled && defaultSystemMode);
    else
      this.render();
  }

  refresh(): void {
    this.render();
  }

  private readonly onTouchStart = (event: TouchEvent): void => {
    if (!this.enabled)
      return;

    const key = this.getKey(event.target);
    if (!key || key === this.passThroughKey)
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
    const hold = this.hold;
    if (
      !hold
      || hold.source !== "touch"
      || hold.key === this.passThroughKey
    )
      return;

    consume(event);
    this.clearHold();
    if (!hold.longPress && hold.key.dataset.key === EMOJI_KEY) {
      if (hold.startedInSystemMode)
        this.toggleControl();
      else
        this.replayShortTouch(hold.key, event);
    }
    this.suppressNextClick = hold.key;
    window.setTimeout(() => {
      if (this.suppressNextClick === hold.key)
        this.suppressNextClick = undefined;
    }, 0);
  };

  private readonly onTouchCancel = (event: TouchEvent): void => {
    if (this.hold?.source !== "touch")
      return;
    consume(event);
    this.clearHold();
  };

  private readonly onGamepadButtonDown = (event: Event): void => {
    const gamepadEvent = event as CustomEvent<GamepadButtonDetail>;
    if (!this.enabled || gamepadEvent.detail?.button !== GAMEPAD_OK_BUTTON)
      return;

    const key = this.getKey(event.target);
    if (!key || key === this.passThroughKey)
      return;
    const isEmoji = key.dataset.key === EMOJI_KEY;
    if (!isEmoji && !this.isSystemKey(key))
      return;

    consume(event);
    if (
      this.hold?.source === "gamepad"
      && this.hold.key === key
      && gamepadEvent.detail.is_repeat
    ) {
      return;
    }
    this.beginHold(key, "gamepad", isEmoji);
    this.hold!.gamepadDetail = {
      ...gamepadEvent.detail,
      is_repeat: false,
    };
    if (!isEmoji)
      this.activateSystemKey(key);
  };

  private readonly onGamepadButtonUp = (event: Event): void => {
    const gamepadEvent = event as CustomEvent<GamepadButtonDetail>;
    const hold = this.hold;
    if (
      gamepadEvent.detail?.button !== GAMEPAD_OK_BUTTON
      || !hold
      || hold.source !== "gamepad"
      || hold.key === this.passThroughKey
    ) {
      return;
    }

    consume(event);
    this.clearHold();
    if (hold.longPress || hold.key.dataset.key !== EMOJI_KEY)
      return;

    if (hold.startedInSystemMode)
      this.toggleControl();
    else
      this.replayGamepadPress(
        hold.key,
        hold.gamepadDetail ?? gamepadEvent.detail,
      );
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
    this.passThroughKey = key;
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
    this.passThroughKey = undefined;
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
    this.passThroughKey = key;
    key.dispatchEvent(new CustomEventConstructor("vgp_onbuttondown", options));
    key.dispatchEvent(new CustomEventConstructor("vgp_onbuttonup", options));
    this.passThroughKey = undefined;
  }

  private beginHold(
    key: HTMLElement,
    source: HoldSource,
    allowLongPress: boolean,
  ): void {
    this.clearHold();
    key.classList.add(PRESSED_KEY_CLASS);
    const hold: HoldState = {
      key,
      longPress: false,
      source,
      startedInSystemMode: this.systemMode,
    };
    this.hold = hold;
    if (!allowLongPress)
      return;
    hold.timer = window.setTimeout(() => {
      hold.timer = undefined;
      hold.longPress = true;
      this.setSystemMode(!this.systemMode);
    }, LONG_PRESS_MS);
  }

  private setSystemMode(active: boolean): void {
    this.systemMode = active;
    this.functionLayer = false;
    if (!active) {
      this.controlActive = false;
      this.altActive = false;
    }
    this.render();
  }

  private toggleControl(): void {
    this.controlActive = !this.controlActive;
    this.render();
  }

  private toggleAlt(): void {
    this.altActive = !this.altActive;
    this.render();
  }

  private releaseModifiers(): void {
    this.controlActive = false;
    this.altActive = false;
    this.render();
  }

  private tapSystemKey(keyName: string): void {
    const withControl = this.controlActive;
    const withAlt = this.altActive;
    this.inputQueue = this.inputQueue
      .then(() => this.sendSystemKey(keyName, withControl, withAlt))
      .then(() => undefined)
      .catch((error) => {
        console.error("[4deus Mod] Failed to send system key", error);
      });
    this.releaseModifiers();
  }

  private isSystemKey(key: HTMLElement): boolean {
    return this.systemMode && (
      key.dataset.key === SYNTHETIC_FUNCTION_KEY
      || isAltKey(key)
      || this.getSystemKeyName(key) !== undefined
    );
  }

  private activateSystemKey(key: HTMLElement): void {
    if (!this.systemMode)
      return;
    if (key.dataset.key === SYNTHETIC_FUNCTION_KEY) {
      this.functionLayer = !this.functionLayer;
      this.render();
      return;
    }
    if (isAltKey(key)) {
      this.toggleAlt();
      return;
    }
    const keyName = this.getSystemKeyName(key);
    if (keyName !== undefined)
      this.tapSystemKey(keyName);
  }

  private getSystemKeyName(key: HTMLElement): string | undefined {
    return resolveSystemKey(
      key,
      this.functionLayer,
      this.controlActive || this.altActive,
    );
  }

  private render(): void {
    this.view.render({
      altActive: this.altActive,
      controlActive: this.controlActive,
      functionLayer: this.functionLayer,
      visible: this.enabled && this.systemMode,
    });
  }

  private clearHold(): void {
    if (!this.hold)
      return;
    this.hold.key.classList.remove(PRESSED_KEY_CLASS);
    if (this.hold.timer !== undefined)
      window.clearTimeout(this.hold.timer);
    this.hold = undefined;
  }
}

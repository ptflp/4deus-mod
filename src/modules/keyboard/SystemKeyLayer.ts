import {
  EMOJI_KEY,
  isAltKey,
  isShiftKey,
  KEY_SELECTOR,
  languageSwitchModifiers,
  LAYOUT_KEY,
  resolveSystemKey,
  SYNTHETIC_FUNCTION_KEY,
} from "./systemKeys";
import type {
  DeckButtonBindings,
  DeckQuickActions,
  LanguageSwitchShortcut,
} from "../../core/settings";
import {
  type DeckButtonCommand,
  resolveDeckButtonCommand,
} from "./deckButtonBindings";
import { DeckButtonBindingView } from "./DeckButtonBindingView";
import { LanguageSwitchMenu } from "./LanguageSwitchMenu";
import { PRESSED_KEY_CLASS, SystemKeyView } from "./SystemKeyView";
import { selectPrimaryKeyboardLayout } from "./steamLayouts";

const LONG_PRESS_MS = 550;
const GAMEPAD_OK_BUTTON = 1;
const SECOND_LAYER_BUTTON = 25;
const HOLDABLE_BOUND_KEYS = new Set([
  "KEY_LEFTCTRL",
  "KEY_LEFTALT",
  "KEY_LEFTSHIFT",
]);
const EMPTY_QUICK_ACTIONS: DeckQuickActions = {
  view: "",
  l1: "",
  r1: "",
  l4: "",
  r4: "",
  l5: "",
  r5: "",
};

export type SystemKeySender = (
  keyName: string,
  withControl: boolean,
  withAlt: boolean,
  withShift: boolean,
  withMeta: boolean,
) => Promise<boolean>;

export type SystemKeyStateSender = (
  keyName: string,
  pressed: boolean,
) => Promise<boolean>;

export interface SystemKeyDiagnostics {
  altActive: boolean;
  controlActive: boolean;
  deckButtonSet: 1 | 2;
  functionLayer: boolean;
  lastSystemKey?: string;
  shiftActive: boolean;
  systemMode: boolean;
}

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

type ChordModifier = "alt" | "shift";

interface ModifierHold {
  identifier?: number;
  key: HTMLElement;
  longPress: boolean;
  modifier: ChordModifier;
  source: HoldSource;
  timer?: number;
}

const consume = (event: Event): void => {
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
};

export class SystemKeyLayer {
  private readonly view = new SystemKeyView();
  private readonly deckButtonBindingView = new DeckButtonBindingView();
  private readonly languageSwitchMenu = new LanguageSwitchMenu();
  private keyboard?: HTMLElement;
  private enabled = false;
  private defaultSystemMode = false;
  private languageSwitchShortcutEnabled = false;
  private languageSwitchShortcut: LanguageSwitchShortcut = "native";
  private deckButtonBindingsEnabled = false;
  private deckButtonBindings: DeckButtonBindings = {
    view: "none",
    l1: "none",
    r1: "none",
    l4: "none",
    r4: "none",
    l5: "none",
    r5: "none",
  };
  private deckButtonQuickActionsEnabled = false;
  private deckButtonQuickActions: DeckQuickActions = {
    view: "",
    l1: "",
    r1: "",
    l4: "",
    r4: "",
    l5: "",
    r5: "",
  };
  private deckButtonSecondLayerEnabled = false;
  private deckButtonSecondLayerActions: DeckQuickActions = {
    view: "",
    l1: "",
    r1: "",
    l4: "",
    r4: "",
    l5: "",
    r5: "",
  };
  private deckButtonSecondLayerActive = false;
  private systemMode = false;
  private functionLayer = false;
  private controlActive = false;
  private altActive = false;
  private shiftActive = false;
  private modifierHold?: ModifierHold;
  private hold?: HoldState;
  private listenerAbort?: AbortController;
  private passThroughKey?: HTMLElement;
  private suppressNextClick?: HTMLElement;
  private inputQueue = Promise.resolve();
  private readonly heldBoundKeys = new Map<number, string>();
  private readonly activeBoundButtons = new Set<number>();
  private lastSystemKey?: string;

  constructor(
    private readonly sendSystemKey: SystemKeySender,
    private readonly setSystemKeyState: SystemKeyStateSender,
    private readonly onLanguageSwitchShortcutChange:
      (shortcut: LanguageSwitchShortcut) => void,
  ) {}

  bind(keyboard: HTMLElement): void {
    this.unbind();
    this.keyboard = keyboard;
    if (this.enabled && this.defaultSystemMode) {
      this.systemMode = true;
      this.functionLayer = false;
    }
    this.view.bind(keyboard);
    this.deckButtonBindingView.bind(keyboard);
    const document = keyboard.ownerDocument;
    this.languageSwitchMenu.bind(document);
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
    this.releaseHeldBoundKeys();
    this.controlActive = false;
    this.altActive = false;
    this.clearModifierHold();
    this.listenerAbort?.abort();
    this.listenerAbort = undefined;
    this.view.unbind();
    this.deckButtonBindingView.unbind();
    this.languageSwitchMenu.unbind();
    this.keyboard = undefined;
    this.systemMode = false;
    this.functionLayer = false;
    this.deckButtonSecondLayerActive = false;
    this.activeBoundButtons.clear();
    this.passThroughKey = undefined;
    this.suppressNextClick = undefined;
  }

  configure(
    enabled: boolean,
    defaultSystemMode: boolean,
    languageSwitchShortcutEnabled: boolean,
    languageSwitchShortcut: LanguageSwitchShortcut,
    deckButtonBindingsEnabled: boolean,
    deckButtonBindings: DeckButtonBindings,
    deckButtonQuickActionsEnabled: boolean,
    deckButtonQuickActions: DeckQuickActions,
    deckButtonSecondLayerEnabled: boolean,
    deckButtonSecondLayerActions: DeckQuickActions,
  ): void {
    const resetMode = !enabled
      || !this.enabled
      || this.defaultSystemMode !== defaultSystemMode;
    this.enabled = enabled;
    this.defaultSystemMode = defaultSystemMode;
    this.languageSwitchShortcutEnabled = languageSwitchShortcutEnabled;
    this.languageSwitchShortcut = languageSwitchShortcut;
    this.deckButtonBindingsEnabled = deckButtonBindingsEnabled;
    this.deckButtonBindings = deckButtonBindings;
    this.deckButtonQuickActionsEnabled = deckButtonQuickActionsEnabled;
    this.deckButtonQuickActions = deckButtonQuickActions;
    this.deckButtonSecondLayerEnabled = deckButtonSecondLayerEnabled;
    this.deckButtonSecondLayerActions = deckButtonSecondLayerActions;
    if (!deckButtonQuickActionsEnabled || !deckButtonSecondLayerEnabled)
      this.deckButtonSecondLayerActive = false;
    if (resetMode)
      this.setSystemMode(enabled && defaultSystemMode);
    else
      this.render();
  }

  refresh(): void {
    this.render();
  }

  getDiagnostics(): SystemKeyDiagnostics {
    return {
      altActive: this.altActive,
      controlActive: this.controlActive,
      deckButtonSet: this.deckButtonSecondLayerActive ? 2 : 1,
      functionLayer: this.functionLayer,
      lastSystemKey: this.lastSystemKey,
      shiftActive: this.shiftActive,
      systemMode: this.systemMode,
    };
  }

  private readonly onTouchStart = (event: TouchEvent): void => {
    if (!this.enabled)
      return;

    const key = this.getKey(event.target);
    if (!key || key === this.passThroughKey)
      return;
    const chordModifier = this.getChordModifier(key);
    if (chordModifier) {
      consume(event);
      this.beginModifierHold(
        key,
        chordModifier,
        "touch",
        event.changedTouches[0]?.identifier,
      );
      return;
    }
    const isEmoji = key.dataset.key === EMOJI_KEY;
    const isLanguageSwitch = this.isLanguageSwitchKey(key);
    if (!isEmoji && !this.isSystemKey(key))
      return;

    consume(event);
    this.beginHold(key, "touch", isEmoji || isLanguageSwitch);
    if (!isEmoji && !isLanguageSwitch)
      this.activateSystemKey(key);
  };

  private readonly onTouchEnd = (event: TouchEvent): void => {
    if (this.endTouchModifierHold(event)) {
      consume(event);
      return;
    }
    const hold = this.hold;
    if (
      !hold
      || hold.source !== "touch"
      || hold.key === this.passThroughKey
    )
      return;

    consume(event);
    this.clearHold();
    if (!hold.longPress)
      this.finishShortTouchHold(hold, event);
    this.suppressClickForTick(hold.key);
  };

  private readonly onTouchCancel = (event: TouchEvent): void => {
    if (this.endTouchModifierHold(event)) {
      consume(event);
      return;
    }
    if (this.hold?.source !== "touch")
      return;
    consume(event);
    this.clearHold();
  };

  private readonly onGamepadButtonDown = (event: Event): void => {
    const gamepadEvent = event as CustomEvent<GamepadButtonDetail>;
    if (!this.enabled)
      return;

    if (this.handleSecondLayerButton(event, gamepadEvent.detail, true))
      return;

    if (this.handleBoundGamepadButtonDown(event, gamepadEvent.detail))
      return;

    this.handleKeyboardGamepadButtonDown(event, gamepadEvent.detail);
  };

  private handleKeyboardGamepadButtonDown(
    event: Event,
    detail: GamepadButtonDetail,
  ): void {
    if (detail?.button !== GAMEPAD_OK_BUTTON)
      return;

    const key = this.getKey(event.target);
    if (!key || key === this.passThroughKey)
      return;
    if (this.handleGamepadChordModifierDown(event, detail, key))
      return;
    if (!this.isInteractiveKey(key))
      return;

    consume(event);
    if (this.isRepeatedGamepadHold(key, detail))
      return;
    const isEmoji = key.dataset.key === EMOJI_KEY;
    const isLanguageSwitch = this.isLanguageSwitchKey(key);
    this.beginHold(key, "gamepad", isEmoji || isLanguageSwitch);
    this.hold!.gamepadDetail = {
      ...detail,
      is_repeat: false,
    };
    if (!isEmoji && !isLanguageSwitch)
      this.activateSystemKey(key);
  }

  private readonly onGamepadButtonUp = (event: Event): void => {
    const gamepadEvent = event as CustomEvent<GamepadButtonDetail>;
    if (this.handleSecondLayerButton(event, gamepadEvent.detail, false))
      return;
    if (this.handleBoundGamepadButtonUp(event, gamepadEvent.detail))
      return;

    if (this.handleGamepadModifierUp(event, gamepadEvent.detail))
      return;

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
    if (hold.longPress)
      return;
    this.finishShortGamepadHold(hold, gamepadEvent.detail);
  };

  private handleGamepadChordModifierDown(
    event: Event,
    detail: GamepadButtonDetail,
    key: HTMLElement,
  ): boolean {
    const modifier = this.getChordModifier(key);
    if (!modifier)
      return false;
    consume(event);
    if (!this.isRepeatedGamepadModifierHold(key, detail))
      this.beginModifierHold(key, modifier, "gamepad");
    return true;
  }

  private isRepeatedGamepadModifierHold(
    key: HTMLElement,
    detail: GamepadButtonDetail,
  ): boolean {
    return Boolean(
      detail.is_repeat
      && this.modifierHold?.source === "gamepad"
      && this.modifierHold.key === key,
    );
  }

  private isRepeatedGamepadHold(
    key: HTMLElement,
    detail: GamepadButtonDetail,
  ): boolean {
    return Boolean(
      detail.is_repeat
      && this.hold?.source === "gamepad"
      && this.hold.key === key,
    );
  }

  private handleGamepadModifierUp(
    event: Event,
    detail: GamepadButtonDetail | undefined,
  ): boolean {
    const hold = this.modifierHold;
    if (detail?.button !== GAMEPAD_OK_BUTTON || hold?.source !== "gamepad")
      return false;
    consume(event);
    this.finishModifierHold(hold);
    return true;
  }

  private readonly onClick = (event: MouseEvent): void => {
    const key = this.getKey(event.target);
    if (!key)
      return;

    if (this.consumeBlockedClick(event, key))
      return;

    if (!this.enabled || !this.systemMode)
      return;

    if (key.dataset.key === EMOJI_KEY) {
      consume(event);
      this.toggleControl();
      return;
    }

    if (this.isSystemKey(key)) {
      if (this.shouldPassNativeLanguageClick(key))
        return;
      consume(event);
      this.activateSystemKey(key);
    }
  };

  private consumeBlockedClick(event: MouseEvent, key: HTMLElement): boolean {
    if (key !== this.modifierHold?.key && key !== this.suppressNextClick)
      return false;
    if (key === this.suppressNextClick)
      this.suppressNextClick = undefined;
    consume(event);
    return true;
  }

  private getKey(target: EventTarget | null): HTMLElement | undefined {
    const candidate = target as Element | null;
    const element = typeof candidate?.closest === "function"
      ? candidate.closest<HTMLElement>(KEY_SELECTOR)
      : null;
    return element && this.keyboard?.contains(element) ? element : undefined;
  }

  private isInteractiveKey(key: HTMLElement): boolean {
    return key.dataset.key === EMOJI_KEY || this.isSystemKey(key);
  }

  private shouldPassNativeLanguageClick(key: HTMLElement): boolean {
    return this.languageSwitchShortcut === "native"
      && this.isLanguageSwitchKey(key);
  }

  private finishShortTouchHold(
    hold: HoldState,
    event: TouchEvent,
  ): void {
    if (hold.key.dataset.key === EMOJI_KEY) {
      if (hold.startedInSystemMode)
        this.toggleControl();
      else
        this.replayShortTouch(hold.key, event);
      return;
    }
    if (this.isLanguageSwitchKey(hold.key))
      this.activateLanguageSwitch(() => this.replayShortTouch(hold.key, event));
  }

  private finishShortGamepadHold(
    hold: HoldState,
    detail: GamepadButtonDetail,
  ): void {
    const replay = (): void => this.replayGamepadPress(
      hold.key,
      hold.gamepadDetail ?? detail,
    );
    if (hold.key.dataset.key === EMOJI_KEY) {
      if (hold.startedInSystemMode)
        this.toggleControl();
      else
        replay();
      return;
    }
    if (this.isLanguageSwitchKey(hold.key))
      this.activateLanguageSwitch(replay);
  }

  private suppressClickForTick(key: HTMLElement): void {
    this.suppressNextClick = key;
    window.setTimeout(() => {
      if (this.suppressNextClick === key)
        this.suppressNextClick = undefined;
    }, 0);
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

  private getChordModifier(key: HTMLElement): ChordModifier | undefined {
    if (!this.systemMode)
      return undefined;
    if (isShiftKey(key) && (this.controlActive || this.altActive))
      return "shift";
    if (isAltKey(key) && (this.controlActive || this.shiftActive))
      return "alt";
    return undefined;
  }

  private beginModifierHold(
    key: HTMLElement,
    modifier: ChordModifier,
    source: HoldSource,
    identifier?: number,
  ): void {
    if (source === "touch" && identifier === undefined)
      return;

    this.clearModifierHold();
    key.classList.add(PRESSED_KEY_CLASS);
    const hold: ModifierHold = {
      identifier,
      key,
      longPress: false,
      modifier,
      source,
    };
    this.modifierHold = hold;
    hold.timer = window.setTimeout(() => {
      hold.timer = undefined;
      hold.longPress = true;
      if (modifier === "shift")
        this.shiftActive = true;
      else
        this.altActive = true;
      this.render();
    }, LONG_PRESS_MS);
  }

  private endTouchModifierHold(event: TouchEvent): boolean {
    const hold = this.modifierHold;
    if (
      !hold
      || hold.source !== "touch"
      || !Array.from(event.changedTouches).some(
        (touch) => touch.identifier === hold.identifier,
      )
    ) {
      return false;
    }

    this.finishModifierHold(hold);
    return true;
  }

  private finishModifierHold(hold: ModifierHold): void {
    const { key, longPress, modifier } = hold;
    this.clearModifierHold();
    if (!longPress) {
      this.tapSystemKey(
        modifier === "shift" ? "KEY_LEFTSHIFT" : "KEY_LEFTALT",
      );
    }
    this.suppressNextClick = key;
    window.setTimeout(() => {
      if (this.suppressNextClick === key)
        this.suppressNextClick = undefined;
    }, 0);
  }

  private clearModifierHold(): void {
    const hold = this.modifierHold;
    if (!hold)
      return;
    hold.key.classList.remove(PRESSED_KEY_CLASS);
    if (hold.timer !== undefined)
      window.clearTimeout(hold.timer);
    this.modifierHold = undefined;
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
      if (this.isLanguageSwitchKey(key)) {
        this.languageSwitchMenu.show(
          this.languageSwitchShortcut,
          this.onLanguageSwitchShortcutChange,
        );
      } else {
        this.setSystemMode(!this.systemMode);
      }
    }, LONG_PRESS_MS);
  }

  private setSystemMode(active: boolean): void {
    this.systemMode = active;
    this.functionLayer = false;
    if (!active) {
      this.controlActive = false;
      this.altActive = false;
      this.clearModifierHold();
      this.shiftActive = false;
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
    this.shiftActive = false;
    this.render();
  }

  private tapSystemKey(keyName: string): void {
    this.tapSystemKeyWithModifiers(
      keyName,
      this.controlActive,
      this.altActive,
      this.shiftActive,
    );
  }

  private tapSystemKeyWithModifiers(
    keyName: string,
    withControl: boolean,
    withAlt: boolean,
    withShift = false,
  ): void {
    this.queueSystemKey(keyName, withControl, withAlt, withShift);
    this.releaseModifiers();
  }

  private tapBoundKey(keyName: string): void {
    this.queueSystemKey(keyName, false, false, false);
  }

  private queueSystemKey(
    keyName: string,
    withControl: boolean,
    withAlt: boolean,
    withShift: boolean,
    withMeta = false,
  ): void {
    this.lastSystemKey = [
      withControl ? "Ctrl" : undefined,
      withAlt ? "Alt" : undefined,
      withShift ? "Shift" : undefined,
      withMeta ? "Meta" : undefined,
      keyName.replace("KEY_", ""),
    ].filter((part) => part !== undefined).join("+");
    this.inputQueue = this.inputQueue
      .then(() =>
        this.sendSystemKey(
          keyName,
          withControl,
          withAlt,
          withShift,
          withMeta,
        ))
      .then(() => undefined)
      .catch((error) => {
        console.error("[4deus Mod] Failed to send system key", error);
      });
  }

  private isSystemKey(key: HTMLElement): boolean {
    return this.systemMode && (
      key.dataset.key === SYNTHETIC_FUNCTION_KEY
      || isAltKey(key)
      || (
        key.dataset.key === LAYOUT_KEY
        && this.languageSwitchShortcutEnabled
      )
      || this.getSystemKeyName(key) !== undefined
    );
  }

  private isLanguageSwitchKey(key: HTMLElement): boolean {
    return this.systemMode
      && !this.functionLayer
      && this.languageSwitchShortcutEnabled
      && key.dataset.key === LAYOUT_KEY;
  }

  private activateLanguageSwitch(replayNative: () => void): void {
    if (this.languageSwitchShortcut === "native") {
      replayNative();
      return;
    }
    selectPrimaryKeyboardLayout();
    const shortcut = languageSwitchModifiers(this.languageSwitchShortcut);
    this.queueSystemKey(
      shortcut.keyName,
      shortcut.withControl,
      shortcut.withAlt,
      false,
      shortcut.withMeta,
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
    if (
      this.isLanguageSwitchKey(key)
      && this.languageSwitchShortcut !== "native"
    ) {
      this.activateLanguageSwitch(() => undefined);
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
      this.controlActive || this.altActive || this.shiftActive,
    );
  }

  private getBoundGamepadCommand(
    buttonCode: number | undefined,
  ): DeckButtonCommand | undefined {
    if (
      !this.deckButtonBindingsEnabled
      || buttonCode === undefined
    ) {
      return undefined;
    }
    const quickActions = this.deckButtonQuickActionsEnabled
      ? this.deckButtonSecondLayerActive
        ? this.deckButtonSecondLayerActions
        : this.deckButtonQuickActions
      : EMPTY_QUICK_ACTIONS;
    return resolveDeckButtonCommand(
      this.deckButtonBindings,
      quickActions,
      buttonCode,
    );
  }

  private isBoundGamepadButton(buttonCode: number | undefined): boolean {
    return this.getBoundGamepadCommand(buttonCode) !== undefined;
  }

  private handleBoundGamepadButtonDown(
    event: Event,
    detail: GamepadButtonDetail | undefined,
  ): boolean {
    const buttonCode = detail?.button;
    const command = this.getBoundGamepadCommand(buttonCode);
    if (!command || buttonCode === undefined)
      return false;
    consume(event);
    this.activeBoundButtons.add(buttonCode);
    if (detail?.is_repeat)
      return true;
    if (command.kind === "chord") {
      const chord = command.chord;
      this.queueSystemKey(
        chord.keyName,
        chord.withControl,
        chord.withAlt,
        chord.withShift,
      );
      return true;
    }
    const action = command.action;
    if (HOLDABLE_BOUND_KEYS.has(action)) {
      const alreadyHeld = Array.from(this.heldBoundKeys.values())
        .includes(action);
      this.heldBoundKeys.set(buttonCode, action);
      if (!alreadyHeld)
        this.queueBoundKeyState(action, true);
    } else {
      this.tapBoundKey(action);
    }
    return true;
  }

  private handleBoundGamepadButtonUp(
    event: Event,
    detail: GamepadButtonDetail | undefined,
  ): boolean {
    const buttonCode = detail?.button;
    if (buttonCode === undefined)
      return false;
    const heldKey = this.heldBoundKeys.get(buttonCode);
    if (heldKey) {
      consume(event);
      this.activeBoundButtons.delete(buttonCode);
      this.heldBoundKeys.delete(buttonCode);
      if (!Array.from(this.heldBoundKeys.values()).includes(heldKey))
        this.queueBoundKeyState(heldKey, false);
      return true;
    }
    if (
      !this.activeBoundButtons.delete(buttonCode)
      && !this.isBoundGamepadButton(buttonCode)
    )
      return false;
    consume(event);
    return true;
  }

  private queueBoundKeyState(keyName: string, pressed: boolean): void {
    this.inputQueue = this.inputQueue
      .then(() => this.setSystemKeyState(keyName, pressed))
      .then(() => undefined)
      .catch((error) => {
        console.error("[4deus Mod] Failed to set system key state", error);
      });
  }

  private releaseHeldBoundKeys(): void {
    const keys = new Set(this.heldBoundKeys.values());
    this.heldBoundKeys.clear();
    keys.forEach((keyName) => this.queueBoundKeyState(keyName, false));
  }

  private handleSecondLayerButton(
    event: Event,
    detail: GamepadButtonDetail | undefined,
    active: boolean,
  ): boolean {
    if (
      !this.deckButtonBindingsEnabled
      || !this.deckButtonQuickActionsEnabled
      || !this.deckButtonSecondLayerEnabled
      || detail?.button !== SECOND_LAYER_BUTTON
    ) {
      return false;
    }
    consume(event);
    if (active && detail.is_repeat)
      return true;
    this.deckButtonSecondLayerActive = active;
    this.render();
    return true;
  }

  private render(): void {
    this.view.render({
      altActive: this.altActive,
      controlActive: this.controlActive,
      functionLayer: this.functionLayer,
      shiftActive: this.shiftActive,
      visible: this.enabled && this.systemMode,
    });
    this.deckButtonBindingView.render(
      this.enabled && this.deckButtonBindingsEnabled,
      this.deckButtonBindings,
      this.deckButtonSecondLayerActive
        ? this.deckButtonSecondLayerActions
        : this.deckButtonQuickActionsEnabled
          ? this.deckButtonQuickActions
          : EMPTY_QUICK_ACTIONS,
      this.deckButtonQuickActionsEnabled
        && this.deckButtonSecondLayerEnabled,
      this.deckButtonSecondLayerActive,
    );
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

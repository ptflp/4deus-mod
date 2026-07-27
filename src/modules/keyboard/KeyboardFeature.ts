import type { ModModule } from "../../core/module";
import type { SettingsStore } from "../../core/settings";
import { buildSecondaryLabelMap } from "./steamLayouts";
import { clearSecondaryLabels, renderSecondaryLabels } from "./secondaryLabels";
import type {
  NativeSteamWindow,
  SteamInputKeyboardEvents,
  WindowInstance,
} from "./types";

const ACTIVE_WINDOW_POLL_MS = 500;
const CHORD_NAVIGATION_DELAY_MS = 75;
const KEYBOARD_ID = "virtual keyboard";
const KEYBOARD_ROUTE = "/keyboard";
const BRING_TO_FRONT_AND_FORCE_OS = 1;

export class KeyboardFeature implements ModModule {
  private activeWindow?: WindowInstance;
  private rootObserver?: MutationObserver;
  private keyboardObserver?: MutationObserver;
  private keyboardElement?: HTMLElement;
  private keyboardRegistration?: { unregister(): void };
  private settingsUnsubscribe?: () => void;
  private windowTimer?: number;
  private refreshFrame?: number;

  constructor(private readonly settings: SettingsStore) {}

  start(): void {
    this.settingsUnsubscribe = this.settings.subscribe(() => this.refresh());
    this.keyboardRegistration = (
      window.SteamClient.Input as unknown as SteamInputKeyboardEvents
    ).RegisterForUserKeyboardMessages?.((event) => {
      const settings = this.settings.getSnapshot().keyboard;
      if (!settings.enabled || !settings.keepOnTop || !event.bChordInvoked)
        return;
      window.setTimeout(() => this.promoteKeyboard(), CHORD_NAVIGATION_DELAY_MS);
    });

    this.bindActiveWindow();
    this.windowTimer = window.setInterval(
      () => this.bindActiveWindow(),
      ACTIVE_WINDOW_POLL_MS,
    );
  }

  stop(): void {
    this.keyboardRegistration?.unregister();
    this.keyboardRegistration = undefined;
    this.settingsUnsubscribe?.();
    this.settingsUnsubscribe = undefined;
    if (this.windowTimer !== undefined)
      window.clearInterval(this.windowTimer);
    this.windowTimer = undefined;
    this.unbindDocument();
  }

  private bindActiveWindow(): void {
    const activeWindow = window.SteamUIStore.ActiveWindowInstance;
    if (activeWindow === this.activeWindow)
      return;

    this.unbindDocument();
    this.activeWindow = activeWindow;
    const document = activeWindow?.BrowserWindow.document;
    if (!document?.documentElement)
      return;

    this.rootObserver = new MutationObserver(() => this.syncKeyboardElement());
    this.rootObserver.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
    this.syncKeyboardElement();
  }

  private unbindDocument(): void {
    this.rootObserver?.disconnect();
    this.rootObserver = undefined;
    this.keyboardObserver?.disconnect();
    this.keyboardObserver = undefined;
    this.keyboardElement = undefined;
    if (this.refreshFrame !== undefined)
      window.cancelAnimationFrame(this.refreshFrame);
    this.refreshFrame = undefined;
    const document = this.activeWindow?.BrowserWindow.document;
    if (document)
      clearSecondaryLabels(document);
    this.activeWindow = undefined;
  }

  private syncKeyboardElement(): void {
    const document = this.activeWindow?.BrowserWindow.document;
    const keyboard = document?.getElementById(KEYBOARD_ID) ?? undefined;
    if (keyboard === this.keyboardElement)
      return;

    this.keyboardObserver?.disconnect();
    this.keyboardObserver = undefined;
    if (document)
      clearSecondaryLabels(document);
    this.keyboardElement = keyboard;

    if (!keyboard)
      return;

    this.keyboardObserver = new MutationObserver(() => this.scheduleRefresh());
    this.keyboardObserver.observe(keyboard, {
      attributes: true,
      attributeFilter: ["data-key", "data-key-col", "data-key-row"],
      childList: true,
      subtree: true,
    });
    this.refresh();
  }

  private scheduleRefresh(): void {
    if (this.refreshFrame !== undefined)
      return;
    this.refreshFrame = window.requestAnimationFrame(() => {
      this.refreshFrame = undefined;
      this.refresh();
    });
  }

  private refresh(): void {
    const document = this.activeWindow?.BrowserWindow.document;
    if (!document)
      return;

    const settings = this.settings.getSnapshot().keyboard;
    const keyboard = this.keyboardElement;
    if (!settings.enabled || !settings.secondaryLabels || !keyboard) {
      clearSecondaryLabels(document);
      return;
    }

    renderSecondaryLabels(
      keyboard,
      buildSecondaryLabelMap(settings.secondaryLayout),
    );
  }

  private promoteKeyboard(): void {
    const instance = window.SteamUIStore.ActiveWindowInstance;
    if (!instance)
      return;

    if (
      instance.LocationPathName !== KEYBOARD_ROUTE
      && instance.NavigateWithoutChangingFocus
    ) {
      instance.VirtualKeyboardManager?.SetVirtualKeyboardHidden?.();
      instance.NavigateWithoutChangingFocus(KEYBOARD_ROUTE, true, true);
    }

    window.setTimeout(() => this.raiseKeyboardWindow(), 0);
    window.setTimeout(() => this.raiseKeyboardWindow(), 50);
  }

  private raiseKeyboardWindow(): void {
    const browserWindow = window.SteamUIStore.ActiveWindowInstance
      ?.BrowserWindow as Window & {
        SteamClient?: {
          Window?: NativeSteamWindow;
        };
      };
    const steamWindow = browserWindow?.SteamClient?.Window;
    steamWindow?.ShowWindow?.();
    steamWindow?.MarkLastFocused?.();
    steamWindow?.BringToFront?.(BRING_TO_FRONT_AND_FORCE_OS);
    steamWindow?.SetKeyFocus?.(true);
  }
}

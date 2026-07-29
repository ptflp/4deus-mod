import type { ModModule } from "../../core/module";
import type { SettingsStore } from "../../core/settings";
import {
  isRelevantKeyboardMutation,
  KEYBOARD_IDENTITY_ATTRIBUTES,
  SHIFT_STATE_ATTRIBUTES,
} from "./keyboardMutations";
import { clearSecondaryLabels, renderSecondaryLabels } from "./secondaryLabels";
import { buildSecondaryLabelMap } from "./steamLayouts";
import {
  SystemKeyLayer,
  type SystemKeySender,
  type SystemKeyStateSender,
} from "./SystemKeyLayer";
import type {
  NativeSteamWindow,
  SteamInputKeyboardEvents,
  WindowInstance,
} from "./types";
import { isVirtualKeyboardVisible } from "./keyboardVisibility";

const ACTIVE_WINDOW_POLL_MS = 500;
const CHORD_NAVIGATION_DELAY_MS = 75;
const DIAGNOSTIC_INTERVAL_MS = 5000;
const KEYBOARD_ID = "virtual keyboard";
const KEYBOARD_ROUTE = "/keyboard";
const SHIFT_KEY_SELECTOR = 'div[data-key-row="3"][data-key-col="0"]';
const BRING_TO_FRONT_AND_FORCE_OS = 1;

export type KeyboardDiagnosticSender = (payload: string) => Promise<boolean>;
export type KeyboardVisibilitySender = (visible: boolean) => Promise<boolean>;

interface DiagnosticError {
  message: string;
  operation: string;
  timestamp: string;
}

const liveDocument = (
  instance: WindowInstance | undefined,
): Document | undefined => {
  try {
    const document = instance?.BrowserWindow.document;
    const ownerWindow = document?.defaultView;
    return document?.documentElement && ownerWindow && !ownerWindow.closed
      ? document
      : undefined;
  } catch {
    return undefined;
  }
};

export class KeyboardFeature implements ModModule {
  private activeWindow?: WindowInstance;
  private activeDocument?: Document;
  private keyboardObserver?: MutationObserver;
  private shiftObserver?: MutationObserver;
  private keyboardElement?: HTMLElement;
  private shiftElement?: HTMLElement;
  private keyboardRegistration?: { unregister(): void };
  private readonly systemKeyLayer: SystemKeyLayer;
  private dismissOnEnterManager?: WindowInstance["VirtualKeyboardManager"];
  private originalDismissOnEnter?: boolean;
  private settingsUnsubscribe?: () => void;
  private windowTimer?: number;
  private refreshFrame?: number;
  private diagnosticTimer?: number;
  private keyboardVisible?: boolean;
  private visibilityQueue = Promise.resolve();
  private refreshCount = 0;
  private observedMutationCount = 0;
  private ignoredMutationCount = 0;
  private lastError?: DiagnosticError;

  constructor(
    private readonly settings: SettingsStore,
    sendSystemKey: SystemKeySender,
    setSystemKeyState: SystemKeyStateSender,
    private readonly sendDiagnostics: KeyboardDiagnosticSender,
    private readonly sendKeyboardVisibility: KeyboardVisibilitySender,
  ) {
    this.systemKeyLayer = new SystemKeyLayer(
      sendSystemKey,
      setSystemKeyState,
      (languageSwitchShortcut) => this.settings.updateKeyboard({
        languageSwitchShortcut,
      }),
    );
  }

  start(): void {
    this.settingsUnsubscribe = this.settings.subscribe(() =>
      this.runSafely("apply settings", () => this.applySettings()),
    );
    this.keyboardRegistration = (
      window.SteamClient.Input as unknown as SteamInputKeyboardEvents
    ).RegisterForUserKeyboardMessages?.((event) => {
      if (event.bChordInvoked)
        this.updateKeyboardVisibility(true);
      const settings = this.settings.getSnapshot().keyboard;
      if (!settings.enabled || !settings.keepOnTop || !event.bChordInvoked)
        return;
      window.setTimeout(
        () => this.runSafely("promote keyboard", () => this.promoteKeyboard()),
        CHORD_NAVIGATION_DELAY_MS,
      );
    });

    this.runSafely("bind active window", () => this.bindActiveWindow());
    this.windowTimer = window.setInterval(
      () => this.runSafely("poll active window", () => this.bindActiveWindow()),
      ACTIVE_WINDOW_POLL_MS,
    );
    this.diagnosticTimer = window.setInterval(
      () => this.runSafely("report diagnostics", () => this.reportDiagnostics()),
      DIAGNOSTIC_INTERVAL_MS,
    );
  }

  stop(): void {
    this.keyboardRegistration?.unregister();
    this.keyboardRegistration = undefined;
    this.settingsUnsubscribe?.();
    this.settingsUnsubscribe = undefined;
    this.restoreDismissOnEnter();
    if (this.windowTimer !== undefined)
      window.clearInterval(this.windowTimer);
    this.windowTimer = undefined;
    if (this.diagnosticTimer !== undefined)
      window.clearInterval(this.diagnosticTimer);
    this.diagnosticTimer = undefined;
    this.unbindDocument(true);
  }

  showKeyboard(): void {
    this.updateKeyboardVisibility(true);
    this.runSafely("show keyboard", () => this.promoteKeyboard());
  }

  private bindActiveWindow(): void {
    const activeWindow = window.SteamUIStore.ActiveWindowInstance;
    const document = liveDocument(activeWindow);
    if (
      activeWindow === this.activeWindow
      && document
      && document === this.activeDocument
    ) {
      if (
        this.keyboardElement?.ownerDocument === document
        && this.keyboardElement.isConnected
      ) {
        this.syncKeyboardVisibility();
      } else {
        this.syncKeyboardElement();
      }
      return;
    }

    this.unbindDocument(false);
    this.activeWindow = activeWindow;
    this.activeDocument = document;
    if (!document) {
      this.syncKeyboardVisibility();
      return;
    }

    this.syncKeyboardElement();
  }

  private unbindDocument(reportHidden: boolean): void {
    this.keyboardObserver?.disconnect();
    this.keyboardObserver = undefined;
    this.shiftObserver?.disconnect();
    this.shiftObserver = undefined;
    this.shiftElement = undefined;
    this.systemKeyLayer.unbind();
    this.keyboardElement = undefined;
    this.restoreDismissOnEnter();
    if (this.refreshFrame !== undefined)
      window.cancelAnimationFrame(this.refreshFrame);
    this.refreshFrame = undefined;
    const document = this.activeDocument;
    if (document?.defaultView)
      clearSecondaryLabels(document);
    this.activeDocument = undefined;
    this.activeWindow = undefined;
    if (reportHidden)
      this.updateKeyboardVisibility(false);
  }

  private syncKeyboardElement(): void {
    const document = liveDocument(this.activeWindow);
    if (!document || document !== this.activeDocument)
      return;
    const keyboard = document?.getElementById(KEYBOARD_ID) ?? undefined;
    if (keyboard === this.keyboardElement) {
      this.syncKeyboardVisibility();
      return;
    }

    this.keyboardObserver?.disconnect();
    this.keyboardObserver = undefined;
    this.shiftObserver?.disconnect();
    this.shiftObserver = undefined;
    this.shiftElement = undefined;
    if (document)
      clearSecondaryLabels(document);
    this.keyboardElement = keyboard;
    this.syncKeyboardVisibility();
    this.applyEnterBehavior();

    if (!keyboard)
      return;

    this.systemKeyLayer.bind(keyboard);
    this.keyboardObserver = new MutationObserver((mutations) => {
      this.runSafely("process keyboard mutations", () =>
        this.processKeyboardMutations(mutations),
      );
    });
    this.keyboardObserver.observe(keyboard, {
      attributes: true,
      attributeFilter: KEYBOARD_IDENTITY_ATTRIBUTES,
      characterData: true,
      childList: true,
      subtree: true,
    });
    this.syncShiftObserver(keyboard);
    this.refresh();
  }

  private processKeyboardMutations(mutations: MutationRecord[]): void {
    const relevantCount = mutations.filter(
      isRelevantKeyboardMutation,
    ).length;
    this.observedMutationCount += mutations.length;
    this.ignoredMutationCount += mutations.length - relevantCount;
    if (relevantCount > 0)
      this.scheduleRefresh();
  }

  private syncShiftObserver(keyboard: HTMLElement): void {
    const shift = keyboard.querySelector<HTMLElement>(SHIFT_KEY_SELECTOR)
      ?? undefined;
    if (shift === this.shiftElement && shift?.isConnected)
      return;
    this.shiftObserver?.disconnect();
    this.shiftObserver = undefined;
    this.shiftElement = shift;
    if (!shift)
      return;
    this.shiftObserver = new MutationObserver((mutations) => {
      this.runSafely("process Shift mutations", () =>
        this.processKeyboardMutations(mutations),
      );
    });
    this.shiftObserver.observe(shift, {
      attributes: true,
      attributeOldValue: true,
      attributeFilter: SHIFT_STATE_ATTRIBUTES,
    });
  }

  private syncKeyboardVisibility(): void {
    this.updateKeyboardVisibility(
      isVirtualKeyboardVisible(
        this.activeWindow?.VirtualKeyboardManager,
        Boolean(this.keyboardElement),
      ),
    );
  }

  private updateKeyboardVisibility(visible: boolean): void {
    if (visible === this.keyboardVisible)
      return;
    this.keyboardVisible = visible;
    this.visibilityQueue = this.visibilityQueue
      .catch(() => undefined)
      .then(async () => {
        await this.sendKeyboardVisibility(visible);
      })
      .catch((error) => {
        console.warn(
          "[4deus Mod] Failed to update keyboard visibility",
          error,
        );
      });
  }

  private scheduleRefresh(): void {
    if (this.refreshFrame !== undefined)
      return;
    this.refreshFrame = window.requestAnimationFrame(() => {
      this.refreshFrame = undefined;
      this.runSafely("refresh keyboard", () => this.refresh());
    });
  }

  private refresh(): void {
    const document = liveDocument(this.activeWindow);
    if (!document || document !== this.activeDocument)
      return;
    const keyboard = this.keyboardElement;
    if (
      keyboard
      && (!keyboard.isConnected || keyboard.ownerDocument !== document)
    ) {
      this.syncKeyboardElement();
      return;
    }
    if (keyboard)
      this.syncShiftObserver(keyboard);
    this.refreshCount += 1;

    const settings = this.settings.getSnapshot().keyboard;
    this.systemKeyLayer.configure(
      settings.enabled,
      settings.systemKeyLayer,
      settings.languageSwitchShortcutEnabled,
      settings.languageSwitchShortcut,
      settings.deckButtonBindingsEnabled,
      settings.deckButtonBindings,
      settings.deckButtonQuickActionsEnabled,
      settings.deckButtonQuickActions,
      settings.deckButtonSecondLayerEnabled,
      settings.deckButtonSecondLayerActions,
    );
    if (!settings.enabled || !settings.secondaryLabels || !keyboard) {
      clearSecondaryLabels(document);
      this.systemKeyLayer.refresh();
      return;
    }

    renderSecondaryLabels(
      keyboard,
      buildSecondaryLabelMap(settings.secondaryLayout),
    );
    this.systemKeyLayer.refresh();
  }

  private applySettings(): void {
    this.applyEnterBehavior();
    this.refresh();
  }

  private reportDiagnostics(): void {
    const settings = this.settings.getSnapshot().keyboard;
    if (!settings.diagnostics) {
      this.resetDiagnosticCounters();
      return;
    }

    const keyboard = this.keyboardElement;
    const payload = JSON.stringify({
      ignoredMutations: this.ignoredMutationCount,
      keyboardPresent: Boolean(keyboard),
      lastError: this.lastError,
      lastFiveSeconds: {
        observedMutations: this.observedMutationCount,
        refreshes: this.refreshCount,
      },
      route: this.activeWindow?.LocationPathName,
      secondaryLabelCount: keyboard
        ?.querySelectorAll(".fourdeus-secondary-label").length ?? 0,
      secondaryLayout: settings.secondaryLayout,
      systemKeyCount: keyboard
        ?.querySelectorAll(".fourdeus-system-key-label").length ?? 0,
      systemLayer: this.systemKeyLayer.getDiagnostics(),
    });
    this.resetDiagnosticCounters();
    void this.sendDiagnostics(payload).catch((error) => {
      console.warn("[4deus Mod] Failed to write keyboard diagnostics", error);
    });
  }

  private resetDiagnosticCounters(): void {
    this.refreshCount = 0;
    this.observedMutationCount = 0;
    this.ignoredMutationCount = 0;
  }

  private runSafely(operation: string, action: () => void): void {
    try {
      action();
    } catch (error) {
      const message = error instanceof Error
        ? `${error.name}: ${error.message}`
        : String(error);
      this.lastError = {
        message,
        operation,
        timestamp: new Date().toISOString(),
      };
      console.error(`[4deus Mod/Keyboard] Failed to ${operation}`, error);
    }
  }

  private applyEnterBehavior(): void {
    const settings = this.settings.getSnapshot().keyboard;
    const manager = this.activeWindow?.VirtualKeyboardManager;
    const shouldOverride = settings.enabled
      && settings.keepOpenAfterEnter
      && Boolean(this.keyboardElement);

    if (!shouldOverride || !manager?.SetDismissOnEnterKey) {
      this.restoreDismissOnEnter();
      return;
    }

    if (manager !== this.dismissOnEnterManager) {
      this.restoreDismissOnEnter();
      this.dismissOnEnterManager = manager;
      this.originalDismissOnEnter = manager.m_bDismissOnEnter;
    }

    manager.SetDismissOnEnterKey(false);
  }

  private restoreDismissOnEnter(): void {
    if (
      this.dismissOnEnterManager?.SetDismissOnEnterKey
      && this.originalDismissOnEnter !== undefined
    ) {
      this.dismissOnEnterManager.SetDismissOnEnterKey(
        this.originalDismissOnEnter,
      );
    }
    this.dismissOnEnterManager = undefined;
    this.originalDismissOnEnter = undefined;
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

    window.setTimeout(
      () => this.runSafely("raise keyboard window", () =>
        this.raiseKeyboardWindow(),
      ),
      0,
    );
    window.setTimeout(
      () => this.runSafely("retry raising keyboard window", () =>
        this.raiseKeyboardWindow(),
      ),
      50,
    );
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

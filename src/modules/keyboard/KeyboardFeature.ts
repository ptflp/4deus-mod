import type { ModModule } from "../../core/module";
import type {
  LanguageSwitchShortcut,
  ModSettings,
  SettingsStore,
} from "../../core/settings";
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
import { shouldAutoSwapVisualLayer } from "./systemKeys";
import { showKeyboardHelp } from "./KeyboardHelpModal";

const ACTIVE_WINDOW_POLL_MS = 500;
const CHORD_NAVIGATION_DELAY_MS = 75;
const DIAGNOSTIC_INTERVAL_MS = 5000;
const KEYBOARD_ID = "virtual keyboard";
const KEYBOARD_ROUTE = "/keyboard";
const KEY_SELECTOR = "div[data-key-row][data-key-col]";
const SHIFT_KEY_SELECTOR = 'div[data-key-row="3"][data-key-col="0"]';
const BRING_TO_FRONT_AND_FORCE_OS = 1;

export type KeyboardDiagnosticSender = (payload: string) => Promise<boolean>;
export type KeyboardVisibilitySender = (visible: boolean) => Promise<boolean>;
export type SharedClipboardReader = () => Promise<string | null>;

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
  private keyboardStructureObserver?: MutationObserver;
  private shiftObserver?: MutationObserver;
  private keyboardElement?: HTMLElement;
  private shiftElement?: HTMLElement;
  private keyboardRegistration?: { unregister(): void };
  private keyboardHelpCloser?: () => void;
  private readonly systemKeyLayer: SystemKeyLayer;
  private dismissOnEnterManager?: WindowInstance["VirtualKeyboardManager"];
  private originalDismissOnEnter?: boolean;
  private pasteManager?: WindowInstance["VirtualKeyboardManager"];
  private originalClientPaste?: () => void;
  private routedClientPaste?: () => void;
  private settingsUnsubscribe?: () => void;
  private appliedKeyboardSettings?: ModSettings["keyboard"];
  private windowTimer?: number;
  private refreshFrame?: number;
  private refreshSystemLayer = false;
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
    private readonly readSharedClipboard: SharedClipboardReader,
  ) {
    this.systemKeyLayer = new SystemKeyLayer(
      sendSystemKey,
      setSystemKeyState,
      (languageSwitchShortcut) => this.setLanguageSwitchShortcut(
        languageSwitchShortcut,
      ),
      () => this.toggleVisualSwap(),
      () => this.autoSwapVisualLayer(),
      {
        close: () => this.closeKeyboardHelp(),
        isVisible: () => this.keyboardHelpCloser !== undefined,
        show: () => this.openKeyboardHelp(),
      },
    );
  }

  start(): void {
    this.appliedKeyboardSettings = this.settings.getSnapshot().keyboard;
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
    this.syncDiagnosticTimer();
  }

  stop(): void {
    this.keyboardRegistration?.unregister();
    this.keyboardRegistration = undefined;
    this.settingsUnsubscribe?.();
    this.settingsUnsubscribe = undefined;
    this.appliedKeyboardSettings = undefined;
    this.restoreDismissOnEnter();
    this.restorePasteRouting();
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

  hideKeyboard(): void {
    this.closeKeyboardHelp();
    this.activeWindow?.VirtualKeyboardManager?.SetVirtualKeyboardHidden?.();
    this.updateKeyboardVisibility(false);
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
        this.syncPasteRouting();
        this.syncKeyboardVisibility();
      } else {
        this.syncKeyboardElement();
      }
      return;
    }

    this.unbindDocument(false);
    this.activeWindow = activeWindow;
    this.activeDocument = document;
    this.syncPasteRouting();
    if (!document) {
      this.syncKeyboardVisibility();
      return;
    }

    this.syncKeyboardElement();
  }

  private unbindDocument(reportHidden: boolean): void {
    this.keyboardObserver?.disconnect();
    this.keyboardObserver = undefined;
    this.keyboardStructureObserver?.disconnect();
    this.keyboardStructureObserver = undefined;
    this.shiftObserver?.disconnect();
    this.shiftObserver = undefined;
    this.shiftElement = undefined;
    this.systemKeyLayer.unbind();
    this.keyboardElement = undefined;
    this.restoreDismissOnEnter();
    this.restorePasteRouting();
    if (this.refreshFrame !== undefined)
      window.cancelAnimationFrame(this.refreshFrame);
    this.refreshFrame = undefined;
    this.refreshSystemLayer = false;
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
    this.keyboardStructureObserver?.disconnect();
    this.keyboardStructureObserver = undefined;
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
        this.processKeyboardMutations(mutations, true),
      );
    });
    this.keyboardObserver.observe(keyboard, {
      attributes: true,
      attributeFilter: KEYBOARD_IDENTITY_ATTRIBUTES,
      subtree: true,
    });
    this.keyboardStructureObserver = new MutationObserver((mutations) => {
      this.runSafely("process keyboard structure", () => {
        const changed = this.processKeyboardMutations(mutations, true);
        if (changed && keyboard === this.keyboardElement)
          this.observeKeyboardStructure(keyboard);
      });
    });
    this.observeKeyboardStructure(keyboard);
    this.syncShiftObserver(keyboard);
    this.refresh();
  }

  private processKeyboardMutations(
    mutations: MutationRecord[],
    refreshSystemLayer: boolean,
  ): boolean {
    let relevantCount = 0;
    for (const mutation of mutations) {
      if (isRelevantKeyboardMutation(mutation))
        relevantCount += 1;
    }
    this.observedMutationCount += mutations.length;
    this.ignoredMutationCount += mutations.length - relevantCount;
    const changed = relevantCount > 0;
    if (changed)
      this.scheduleRefresh(refreshSystemLayer);
    return changed;
  }

  private observeKeyboardStructure(keyboard: HTMLElement): void {
    const observer = this.keyboardStructureObserver;
    if (!observer)
      return;
    observer.disconnect();
    const targets = new Set<HTMLElement>([keyboard]);
    keyboard.querySelectorAll<HTMLElement>(KEY_SELECTOR).forEach((key) =>
      this.addKeyAncestors(key, keyboard, targets));
    targets.forEach((target) => observer.observe(target, { childList: true }));
  }

  private addKeyAncestors(
    key: HTMLElement,
    keyboard: HTMLElement,
    targets: Set<HTMLElement>,
  ): void {
    let ancestor = key.parentElement;
    while (ancestor && ancestor !== keyboard) {
      targets.add(ancestor);
      ancestor = ancestor.parentElement;
    }
  }

  private syncShiftObserver(keyboard: HTMLElement): void {
    if (
      this.shiftElement?.isConnected
      && this.shiftElement.ownerDocument === keyboard.ownerDocument
      && keyboard.contains(this.shiftElement)
    ) {
      return;
    }
    const shift = keyboard.querySelector<HTMLElement>(SHIFT_KEY_SELECTOR)
      ?? undefined;
    this.shiftObserver?.disconnect();
    this.shiftObserver = undefined;
    this.shiftElement = shift;
    if (!shift)
      return;
    this.shiftObserver = new MutationObserver((mutations) => {
      this.runSafely("process Shift mutations", () =>
        this.processKeyboardMutations(mutations, false),
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

  private scheduleRefresh(refreshSystemLayer: boolean): void {
    this.refreshSystemLayer ||= refreshSystemLayer;
    if (this.refreshFrame !== undefined)
      return;
    this.refreshFrame = window.requestAnimationFrame(() => {
      this.refreshFrame = undefined;
      const shouldRefreshSystemLayer = this.refreshSystemLayer;
      this.refreshSystemLayer = false;
      this.runSafely(
        "refresh keyboard",
        () => this.refresh(shouldRefreshSystemLayer),
      );
    });
  }

  private refresh(refreshSystemLayer = true): void {
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
    this.configureSystemKeyLayer(settings, refreshSystemLayer);
    if (!settings.enabled || !settings.secondaryLabels || !keyboard) {
      clearSecondaryLabels(document);
      this.refreshSystemKeys(refreshSystemLayer);
      return;
    }

    renderSecondaryLabels(
      keyboard,
      buildSecondaryLabelMap(
        settings.secondaryLayout,
        settings.secondaryLabelsQwertyOnly,
      ),
      settings.secondaryLayerSwapped,
    );
    this.refreshSystemKeys(refreshSystemLayer);
  }

  private configureSystemKeyLayer(
    settings: ModSettings["keyboard"],
    enabled: boolean,
  ): void {
    if (!enabled)
      return;
    this.systemKeyLayer.configure(
      settings.enabled,
      settings.systemKeyLayer,
      settings.holdHints,
      settings.languageSwitchShortcutEnabled,
      settings.languageSwitchShortcut,
      settings.deckButtonBindingsEnabled,
      settings.deckButtonBindings,
      settings.deckButtonQuickActionsEnabled,
      settings.deckButtonQuickActions,
      settings.deckButtonSecondLayerEnabled,
      settings.deckButtonSecondLayerActions,
    );
  }

  private refreshSystemKeys(enabled: boolean): void {
    if (enabled)
      this.systemKeyLayer.refresh();
  }

  private applySettings(): void {
    const settings = this.settings.getSnapshot().keyboard;
    if (settings === this.appliedKeyboardSettings)
      return;
    this.appliedKeyboardSettings = settings;
    this.syncDiagnosticTimer();
    this.applyEnterBehavior();
    this.refresh();
  }

  private setLanguageSwitchShortcut(
    languageSwitchShortcut: LanguageSwitchShortcut,
  ): void {
    this.settings.updateKeyboard({
      languageSwitchShortcut,
    });
  }

  private toggleVisualSwap(): boolean {
    const keyboard = this.settings.getSnapshot().keyboard;
    if (
      !keyboard.enabled
      || !keyboard.secondaryLabels
      || !this.keyboardElement
    ) {
      return false;
    }
    const labels = buildSecondaryLabelMap(
      keyboard.secondaryLayout,
      keyboard.secondaryLabelsQwertyOnly,
    );
    if (labels.size === 0)
      return false;
    this.settings.updateKeyboard({
      secondaryLayerSwapped: !keyboard.secondaryLayerSwapped,
    });
    return true;
  }

  private autoSwapVisualLayer(): void {
    const keyboard = this.settings.getSnapshot().keyboard;
    if (shouldAutoSwapVisualLayer(
      keyboard.autoSwapVisualLayer,
      keyboard.languageSwitchShortcut,
    )) {
      this.toggleVisualSwap();
    }
  }

  private openKeyboardHelp(): void {
    this.closeKeyboardHelp();
    let close: (() => void) | undefined;
    close = showKeyboardHelp({
      keyboard: this.keyboardElement,
      onClosed: () => {
        if (this.keyboardHelpCloser === close)
          this.keyboardHelpCloser = undefined;
      },
      parent: this.keyboardElement?.ownerDocument.defaultView ?? undefined,
    });
    this.keyboardHelpCloser = close;
  }

  private closeKeyboardHelp(): void {
    const close = this.keyboardHelpCloser;
    this.keyboardHelpCloser = undefined;
    close?.();
  }

  private syncDiagnosticTimer(): void {
    const enabled = this.settings.getSnapshot().keyboard.diagnostics;
    if (enabled && this.diagnosticTimer === undefined) {
      this.diagnosticTimer = window.setInterval(
        () =>
          this.runSafely(
            "report diagnostics",
            () => this.reportDiagnostics(),
          ),
        DIAGNOSTIC_INTERVAL_MS,
      );
      return;
    }
    if (enabled || this.diagnosticTimer === undefined)
      return;
    window.clearInterval(this.diagnosticTimer);
    this.diagnosticTimer = undefined;
    this.resetDiagnosticCounters();
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

  private syncPasteRouting(): void {
    const manager = this.activeWindow?.VirtualKeyboardManager;
    if (
      manager === this.pasteManager
      && manager?.SendClientPasteCommand === this.routedClientPaste
    ) {
      return;
    }
    this.restorePasteRouting();
    const original = manager?.SendClientPasteCommand;
    if (!manager || typeof original !== "function")
      return;

    const fallback = original.bind(manager);
    const routed = () => {
      void this.routePaste(fallback);
    };
    manager.SendClientPasteCommand = routed;
    this.pasteManager = manager;
    this.originalClientPaste = original;
    this.routedClientPaste = routed;
  }

  private restorePasteRouting(): void {
    const manager = this.pasteManager;
    if (
      manager
      && manager.SendClientPasteCommand === this.routedClientPaste
    ) {
      manager.SendClientPasteCommand = this.originalClientPaste;
    }
    this.pasteManager = undefined;
    this.originalClientPaste = undefined;
    this.routedClientPaste = undefined;
  }

  private async routePaste(fallback: () => void): Promise<void> {
    try {
      const text = await this.readSharedClipboard();
      const input = (
        window.SteamClient.Input as unknown as SteamInputKeyboardEvents
      );
      if (
        text !== null
        && typeof input.ControllerKeyboardSendText === "function"
      ) {
        input.ControllerKeyboardSendText(text);
        return;
      }
    } catch (error) {
      console.warn(
        "[4deus Mod/Keyboard] Shared clipboard paste failed",
        error,
      );
    }
    fallback();
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

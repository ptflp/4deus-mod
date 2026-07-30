import { appBridgeTranslations } from "./appBridgeTranslations";
import { nestedDesktopTranslations } from "./nestedDesktopTranslations";
import { systemToolsTranslations } from "./systemToolsTranslations";

export interface Strings {
  keyboard: string;
  enabled: string;
  enabledDescription: string;
  keepOnTop: string;
  keepOnTopDescription: string;
  keepOpenAfterEnter: string;
  keepOpenAfterEnterDescription: string;
  systemKeyLayer: string;
  systemKeyLayerDescription: string;
  holdHints: string;
  holdHintsDescription: string;
  keyboardHelpTitle: string;
  keyboardHelpSystemLayerDescription: string;
  keyboardHelpLanguageMenuDescription: string;
  keyboardHelpSwapDescription: string;
  keyboardHelpAutoSwapDescription: string;
  keyboardHelpPosition: string;
  keyboardHelpPositionDescription: string;
  languageSwitchShortcut: string;
  languageSwitchShortcutDescription: string;
  languageSwitchShortcutChoice: string;
  deckButtonBindings: string;
  deckButtonBindingsDescription: string;
  keyBinding: string;
  quickAction: string;
  quickActionsDescription: string;
  quickActionHint: string;
  invalidQuickAction: string;
  secondHotkeyLayer: string;
  secondHotkeyLayerDescription: string;
  hotkeys: string;
  quickActions: string;
  appBridge: string;
  appBridgeEnabledDescription: string;
  appBridgeQuickSetup: string;
  appBridgeParsecDescription: string;
  addOrFixParsec: string;
  appBridgeRustDeskDescription: string;
  addOrFixRustDesk: string;
  appBridgeApplications: string;
  appBridgeSelectApplication: string;
  appBridgeLoadApplications: string;
  appBridgeName: string;
  appBridgeExecutable: string;
  appBridgeArguments: string;
  appBridgeWorkingDirectory: string;
  appBridgeTrackProcess: string;
  appBridgeClearSteamRuntime: string;
  appBridgeForceX11: string;
  appBridgeLibraryPath: string;
  addOrFixApplication: string;
  appBridgeReady: string;
  systemTools: string;
  systemToolsDescription: string;
  systemToolsStatus: string;
  systemToolsLoading: string;
  mangoHudFix: string;
  mangoHudFixDescription: string;
  mangoHudFixInstalled: string;
  mangoHudFixNeedsRepair: string;
  mangoHudFixNotInstalled: string;
  mangoHudFixUnavailable: string;
  installOrRepairMangoHudFix: string;
  removeMangoHudFix: string;
  mangoHudFixApplied: string;
  mangoHudFixRemoved: string;
  steamOsApplication: string;
  steamOsApplicationDescription: string;
  addOrRepairSteamOsApplication: string;
  steamOsApplicationReady: string;
  nestedDesktopMouseBridge: string;
  nestedDesktopMouseBridgeDescription: string;
  nestedDesktopTrackpadInertia: string;
  nestedDesktopTrackpadInertiaDescription: string;
  rustDeskPointerFix: string;
  rustDeskPointerFixDescription: string;
  rustDeskFocusOnInput: string;
  rustDeskFocusOnInputDescription: string;
  rustDeskScrollInertia: string;
  rustDeskScrollInertiaDescription: string;
  controller: string;
  trackpadAutoRecovery: string;
  trackpadAutoRecoveryDescription: string;
  nestedDesktopHotkeys: string;
  nestedDesktopHotkeysDescription: string;
  nestedDesktopHotkeysEnabled: string;
  nestedDesktopHotkeysEnabledDescription: string;
  resetNestedDesktopHotkeys: string;
  nestedDesktopHotkeysReset: string;
  labels: string;
  labelsDescription: string;
  secondaryLayout: string;
  secondaryLayoutDescription: string;
  swapKeys: string;
  autoSwapVisualLayer: string;
  autoSwapVisualLayerDescription: string;
  secondaryLabelsQwertyOnly: string;
  secondaryLabelsQwertyOnlyDescription: string;
  automatic: string;
  diagnostics: string;
  diagnosticsDescription: string;
  pluginSettings: string;
  developerMode: string;
  developerModeDescription: string;
  trackpadMetrics: string;
  trackpadMetricsDescription: string;
  trackpadMetricsPrivacy: string;
  trackpadMetricsCaptureDescription: string;
  trackpadMetricsLiveBuffer: string;
  trackpadMetricsSaveCapture: string;
  trackpadMetricsClearBuffer: string;
  trackpadMetricsCaptures: string;
  trackpadMetricsLive: string;
  trackpadMetricsNoData: string;
  trackpadMetricsDeleteCapture: string;
  trackpadMetricsManual: string;
  trackpadMetricsRunning: string;
  trackpadMetricsStopped: string;
  trackpadMetricsDevice: string;
  trackpadMetricsRetention: string;
  trackpadMetricsSamples: string;
  trackpadMetricsPressure: string;
  trackpadMetricsTouched: string;
  trackpadMetricsPressed: string;
  trackpadMetricsLeft: string;
  trackpadMetricsRight: string;
  trackpadMetricsEnableDeveloperFirst: string;
  trackpadMetricsCaptureSaved: string;
  trackpadMetricsClearConfirmation: string;
  trackpadMetricsClearCancel: string;
  trackpadMetricsJournal: string;
  trackpadMetricsToggleConfirmation: string;
  trackpadMetricsConfirm: string;
}

type Values = [
  keyboard: string,
  enabled: string,
  enabledDescription: string,
  keepOnTop: string,
  keepOnTopDescription: string,
  keepOpenAfterEnter: string,
  keepOpenAfterEnterDescription: string,
  systemKeyLayer: string,
  systemKeyLayerDescription: string,
  labels: string,
  labelsDescription: string,
  secondaryLayout: string,
  secondaryLayoutDescription: string,
  automatic: string,
  diagnostics?: string,
  diagnosticsDescription?: string,
  languageSwitchShortcut?: string,
  languageSwitchShortcutDescription?: string,
  languageSwitchShortcutChoice?: string,
  deckButtonBindings?: string,
  deckButtonBindingsDescription?: string,
  keyBinding?: string,
  quickAction?: string,
  quickActionsDescription?: string,
  quickActionHint?: string,
  invalidQuickAction?: string,
  secondHotkeyLayer?: string,
  secondHotkeyLayerDescription?: string,
  appBridge?: string,
  appBridgeEnabledDescription?: string,
  appBridgeQuickSetup?: string,
  appBridgeParsecDescription?: string,
  addOrFixParsec?: string,
  appBridgeApplications?: string,
  appBridgeSelectApplication?: string,
  appBridgeLoadApplications?: string,
  appBridgeName?: string,
  appBridgeExecutable?: string,
  appBridgeArguments?: string,
  appBridgeWorkingDirectory?: string,
  appBridgeTrackProcess?: string,
  appBridgeClearSteamRuntime?: string,
  appBridgeForceX11?: string,
  appBridgeLibraryPath?: string,
  addOrFixApplication?: string,
  appBridgeReady?: string,
  appBridgeRustDeskDescription?: string,
  addOrFixRustDesk?: string,
  hotkeys?: string,
  quickActions?: string,
  holdHints?: string,
  holdHintsDescription?: string,
  keyboardHelpTitle?: string,
  keyboardHelpSystemLayerDescription?: string,
  keyboardHelpLanguageMenuDescription?: string,
  keyboardHelpSwapDescription?: string,
  keyboardHelpAutoSwapDescription?: string,
  keyboardHelpPosition?: string,
  keyboardHelpPositionDescription?: string,
  swapKeys?: string,
  autoSwapVisualLayer?: string,
  autoSwapVisualLayerDescription?: string,
  secondaryLabelsQwertyOnly?: string,
  secondaryLabelsQwertyOnlyDescription?: string,
  pluginSettings?: string,
  developerMode?: string,
  developerModeDescription?: string,
  trackpadMetrics?: string,
  trackpadMetricsDescription?: string,
  trackpadMetricsPrivacy?: string,
  trackpadMetricsCaptureDescription?: string,
  trackpadMetricsLiveBuffer?: string,
  trackpadMetricsSaveCapture?: string,
  trackpadMetricsClearBuffer?: string,
  trackpadMetricsCaptures?: string,
  trackpadMetricsLive?: string,
  trackpadMetricsNoData?: string,
  trackpadMetricsDeleteCapture?: string,
  trackpadMetricsManual?: string,
  trackpadMetricsRunning?: string,
  trackpadMetricsStopped?: string,
  trackpadMetricsDevice?: string,
  trackpadMetricsRetention?: string,
  trackpadMetricsSamples?: string,
  trackpadMetricsPressure?: string,
  trackpadMetricsTouched?: string,
  trackpadMetricsPressed?: string,
  trackpadMetricsLeft?: string,
  trackpadMetricsRight?: string,
  trackpadMetricsEnableDeveloperFirst?: string,
  trackpadMetricsCaptureSaved?: string,
  trackpadMetricsClearConfirmation?: string,
  trackpadMetricsClearCancel?: string,
  trackpadMetricsJournal?: string,
  trackpadMetricsToggleConfirmation?: string,
  trackpadMetricsConfirm?: string,
];

const define = ([
  keyboard,
  enabled,
  enabledDescription,
  keepOnTop,
  keepOnTopDescription,
  keepOpenAfterEnter,
  keepOpenAfterEnterDescription,
  systemKeyLayer,
  systemKeyLayerDescription,
  labels,
  labelsDescription,
  secondaryLayout,
  secondaryLayoutDescription,
  automatic,
  diagnostics = "Keyboard diagnostics",
  diagnosticsDescription = "Write keyboard state and performance counters to the Decky log every five seconds; turns off when the plugin restarts",
  languageSwitchShortcut = "System language shortcut",
  languageSwitchShortcutDescription = "Tap the layout key to switch language; hold it to choose a shortcut or swap the visual key layers",
  languageSwitchShortcutChoice = "Language shortcut",
  deckButtonBindings = "Steam Deck button bindings",
  deckButtonBindingsDescription = "Use shoulder, trigger, stick-click, or rear buttons as keys while the virtual keyboard is open",
  keyBinding = "Key",
  quickAction = "Quick action",
  quickActionsDescription = "Enable custom one-button key combinations; valid combinations override regular bindings",
  quickActionHint = "Example: Ctrl+Shift+Delete",
  invalidQuickAction = "Invalid combination; the regular binding will be used",
  secondHotkeyLayer = "Second hotkey set with R4",
  secondHotkeyLayerDescription = "Hold R4 to use the second quick-action set; R4's own binding is overridden",
  appBridge = "App Bridge",
  appBridgeEnabledDescription = "Add third-party applications to Gaming Mode through configurable compatibility profiles",
  appBridgeQuickSetup = "Quick setup",
  appBridgeParsecDescription = "Add Parsec or repair its Steam shortcut with the tested process-tracking profile",
  addOrFixParsec = "Add / Fix Parsec",
  appBridgeApplications = "Applications",
  appBridgeSelectApplication = "Installed application",
  appBridgeLoadApplications = "Reload installed applications",
  appBridgeName = "Shortcut name",
  appBridgeExecutable = "Executable",
  appBridgeArguments = "Arguments",
  appBridgeWorkingDirectory = "Working directory",
  appBridgeTrackProcess = "Keep Steam session for process",
  appBridgeClearSteamRuntime = "Clear Steam preload",
  appBridgeForceX11 = "Force Gamescope/X11 environment",
  appBridgeLibraryPath = "Compatibility library path",
  addOrFixApplication = "Add / Fix application",
  appBridgeReady = "Profile and Steam shortcut are ready",
  appBridgeRustDeskDescription = "Add RustDesk or repair its Steam shortcut with the Gamescope/X11 compatibility profile",
  addOrFixRustDesk = "Add / Fix RustDesk",
  hotkeys = "Hotkeys",
  quickActions = "Quick actions",
  holdHints = "Hold hints",
  holdHintsDescription = "Show a small Hold badge on keys with a long-press action",
  keyboardHelpTitle = "Keyboard guide",
  keyboardHelpSystemLayerDescription = "Hold Ctrl to switch between the regular keyboard and system keys",
  keyboardHelpLanguageMenuDescription = "Hold the language key to choose Steam, Alt + Shift, Ctrl + Shift, or Cmd + Space",
  keyboardHelpSwapDescription = "Use 1 ⇄ 2 to manually align the visible letters with the active system language",
  keyboardHelpAutoSwapDescription = "After the first manual alignment, automatic swap follows each system language switch",
  keyboardHelpPosition = "Keyboard position",
  keyboardHelpPositionDescription = "Press Menu, the right-side button opposite View, to move the keyboard between the top and bottom of the screen",
  swapKeys = "Swap primary and secondary keys",
  autoSwapVisualLayer = "Auto-swap after language switch",
  autoSwapVisualLayerDescription = "After a system language shortcut, swap the primary and secondary key labels to stay synchronized",
  secondaryLabelsQwertyOnly = "Second layer only on QWERTY",
  secondaryLabelsQwertyOnlyDescription = "Hide secondary symbols on every other Steam keyboard layout, including layouts added later",
  pluginSettings = "Plugin settings",
  developerMode = "Developer mode",
  developerModeDescription = "Show diagnostic and experimental plugin tools",
  trackpadMetrics = "Trackpad metrics",
  trackpadMetricsDescription = "Keep a low-overhead 15-minute live history plus three append-only 15-minute journal windows",
  trackpadMetricsPrivacy = "Stored only on this Steam Deck and never sent anywhere",
  trackpadMetricsCaptureDescription = "The journal appends every three minutes and immediately on suspicious pressure; manual captures remain until you delete them",
  trackpadMetricsLiveBuffer = "Live buffer",
  trackpadMetricsSaveCapture = "Save current buffer",
  trackpadMetricsClearBuffer = "Clear live buffer",
  trackpadMetricsCaptures = "Saved captures",
  trackpadMetricsLive = "Live",
  trackpadMetricsNoData = "No trackpad samples yet",
  trackpadMetricsDeleteCapture = "Delete capture",
  trackpadMetricsManual = "Manual",
  trackpadMetricsRunning = "Collecting",
  trackpadMetricsStopped = "Stopped",
  trackpadMetricsDevice = "Device",
  trackpadMetricsRetention = "History",
  trackpadMetricsSamples = "Samples",
  trackpadMetricsPressure = "Pressure",
  trackpadMetricsTouched = "Touch",
  trackpadMetricsPressed = "Click",
  trackpadMetricsLeft = "Left",
  trackpadMetricsRight = "Right",
  trackpadMetricsEnableDeveloperFirst = "Enable Developer mode to use trackpad diagnostics",
  trackpadMetricsCaptureSaved = "The live buffer was pinned as a saved capture",
  trackpadMetricsClearConfirmation = "The live RAM buffer will be cleared. Saved captures and append-only journal windows will not be affected.",
  trackpadMetricsClearCancel = "Cancel",
  trackpadMetricsJournal = "Automatic journal",
  trackpadMetricsToggleConfirmation = "Confirm changing trackpad metrics collection. The confirmation button unlocks after five seconds.",
  trackpadMetricsConfirm = "Confirm",
]: Values): Strings => ({
  keyboard,
  enabled,
  enabledDescription,
  keepOnTop,
  keepOnTopDescription,
  keepOpenAfterEnter,
  keepOpenAfterEnterDescription,
  systemKeyLayer,
  systemKeyLayerDescription,
  holdHints,
  holdHintsDescription,
  keyboardHelpTitle,
  keyboardHelpSystemLayerDescription,
  keyboardHelpLanguageMenuDescription,
  keyboardHelpSwapDescription,
  keyboardHelpAutoSwapDescription,
  keyboardHelpPosition,
  keyboardHelpPositionDescription,
  languageSwitchShortcut,
  languageSwitchShortcutDescription,
  languageSwitchShortcutChoice,
  deckButtonBindings,
  deckButtonBindingsDescription,
  keyBinding,
  quickAction,
  quickActionsDescription,
  quickActionHint,
  invalidQuickAction,
  secondHotkeyLayer,
  secondHotkeyLayerDescription,
  hotkeys,
  quickActions,
  appBridge,
  appBridgeEnabledDescription,
  appBridgeQuickSetup,
  appBridgeParsecDescription,
  addOrFixParsec,
  appBridgeApplications,
  appBridgeSelectApplication,
  appBridgeLoadApplications,
  appBridgeName,
  appBridgeExecutable,
  appBridgeArguments,
  appBridgeWorkingDirectory,
  appBridgeTrackProcess,
  appBridgeClearSteamRuntime,
  appBridgeForceX11,
  appBridgeLibraryPath,
  addOrFixApplication,
  appBridgeReady,
  appBridgeRustDeskDescription,
  addOrFixRustDesk,
  systemTools: "System Tools",
  systemToolsDescription: "Install and manage narrowly scoped system fixes",
  systemToolsStatus: "Status",
  systemToolsLoading: "Loading…",
  mangoHudFix: "MangoHud Nested Desktop fix",
  mangoHudFixDescription: "Prevents protected Nested Desktop processes from crashing MangoApp and hiding the performance overlay",
  mangoHudFixInstalled: "Installed",
  mangoHudFixNeedsRepair: "Update or repair required",
  mangoHudFixNotInstalled: "Not installed",
  mangoHudFixUnavailable: "Unavailable on this system",
  installOrRepairMangoHudFix: "Install / Repair fix",
  removeMangoHudFix: "Remove fix",
  mangoHudFixApplied: "MangoHud fix installed",
  mangoHudFixRemoved: "MangoHud fix removed",
  steamOsApplication: "SteamOS in Gaming Mode",
  steamOsApplicationDescription: "Adds or repairs a fully configured Nested Desktop shortcut in the Steam library",
  addOrRepairSteamOsApplication: "Add / Repair SteamOS",
  steamOsApplicationReady: "SteamOS application is ready",
  nestedDesktopMouseBridge: "Nested Desktop mouse over games",
  nestedDesktopMouseBridgeDescription: "Restores the right-trackpad cursor and click in Nested Desktop while another Game Mode app is running",
  nestedDesktopTrackpadInertia: "Trackpad inertia",
  nestedDesktopTrackpadInertiaDescription: "Continues cursor and scroll movement after a fast swipe; disable to stop immediately when a trackpad is released",
  rustDeskPointerFix: "RustDesk pointer fix",
  rustDeskPointerFixDescription: "Prevents duplicate cursors and pointer teleportation in Nested Desktop; Add / Fix RustDesk installs the required system hook automatically",
  rustDeskFocusOnInput: "Focus Nested Desktop on RustDesk input",
  rustDeskFocusOnInputDescription: "⚠ Brings Nested Desktop to the foreground on RustDesk pointer or keyboard input. This bypasses Steam's PIN lock screen. Disabled by default; enabling it means you accept this risk",
  rustDeskScrollInertia: "RustDesk wheel inertia",
  rustDeskScrollInertiaDescription: "Adds a short natural glide after fast wheel scrolling; disabled by default and does not affect trackpad inertia",
  controller: "Controller",
  trackpadAutoRecovery: "Automatic trackpad recovery",
  trackpadAutoRecoveryDescription: "Automatically recovers frozen or stuck trackpads. Disabled by default",
  nestedDesktopHotkeys: "Nested Desktop bindings",
  nestedDesktopHotkeysDescription: "Configure controls sent directly to Nested Desktop, including while a game is running in parallel",
  nestedDesktopHotkeysEnabled: "Controller bindings",
  nestedDesktopHotkeysEnabledDescription: "Send configured keyboard and mouse actions while Nested Desktop has focus",
  resetNestedDesktopHotkeys: "Reset to Steam defaults",
  nestedDesktopHotkeysReset: "Nested Desktop bindings reset",
  labels,
  labelsDescription,
  secondaryLayout,
  secondaryLayoutDescription,
  swapKeys,
  autoSwapVisualLayer,
  autoSwapVisualLayerDescription,
  secondaryLabelsQwertyOnly,
  secondaryLabelsQwertyOnlyDescription,
  automatic,
  diagnostics,
  diagnosticsDescription,
  pluginSettings,
  developerMode,
  developerModeDescription,
  trackpadMetrics,
  trackpadMetricsDescription,
  trackpadMetricsPrivacy,
  trackpadMetricsCaptureDescription,
  trackpadMetricsLiveBuffer,
  trackpadMetricsSaveCapture,
  trackpadMetricsClearBuffer,
  trackpadMetricsCaptures,
  trackpadMetricsLive,
  trackpadMetricsNoData,
  trackpadMetricsDeleteCapture,
  trackpadMetricsManual,
  trackpadMetricsRunning,
  trackpadMetricsStopped,
  trackpadMetricsDevice,
  trackpadMetricsRetention,
  trackpadMetricsSamples,
  trackpadMetricsPressure,
  trackpadMetricsTouched,
  trackpadMetricsPressed,
  trackpadMetricsLeft,
  trackpadMetricsRight,
  trackpadMetricsEnableDeveloperFirst,
  trackpadMetricsCaptureSaved,
  trackpadMetricsClearConfirmation,
  trackpadMetricsClearCancel,
  trackpadMetricsJournal,
  trackpadMetricsToggleConfirmation,
  trackpadMetricsConfirm,
});

export const english = define([
  "Keyboard",
  "Enable keyboard module",
  "Enable keyboard fixes and customization",
  "Keep keyboard on top",
  "Bring the Steam keyboard above application windows",
  "Keep open after Enter",
  "Do not dismiss the keyboard after pressing Enter",
  "System keys by default",
  "Show Ctrl, Fn, Esc, Delete, and F1-F12 on open; hold the Steam items key to switch layers",
  "Secondary key labels",
  "Show letters from another enabled Steam layout",
  "Secondary layout",
  "Automatic follows an enabled layout that is not currently active",
  "Automatic",
  "Keyboard diagnostics",
  "Write keyboard state and performance counters to the Decky log every five seconds; turns off when the plugin restarts",
  "System language shortcut",
  "Tap the layout key to switch language; hold it to choose a shortcut or swap the visual key layers",
  "Language shortcut",
  "Steam Deck button bindings",
  "Use shoulder, trigger, stick-click, or rear buttons as keys while the virtual keyboard is open",
  "Key",
  "Quick action",
  "Enable custom one-button key combinations; valid combinations override regular bindings",
  "Example: Ctrl+Shift+Delete",
  "Invalid combination; the regular binding will be used",
  "Second hotkey set with R4",
  "Hold R4 to use the second quick-action set; R4's own binding is overridden",
  "App Bridge",
  "Add third-party applications to Gaming Mode through configurable compatibility profiles",
  "Quick setup",
  "Add Parsec or repair its Steam shortcut with the tested process-tracking profile",
  "Add / Fix Parsec",
  "Applications",
  "Installed application",
  "Reload installed applications",
  "Shortcut name",
  "Executable",
  "Arguments",
  "Working directory",
  "Keep Steam session for process",
  "Clear Steam preload",
  "Force Gamescope/X11 environment",
  "Compatibility library path",
  "Add / Fix application",
  "Profile and Steam shortcut are ready",
  "Add RustDesk or repair its Steam shortcut with the Gamescope/X11 compatibility profile",
  "Add / Fix RustDesk",
  "Hotkeys",
  "Quick actions",
  "Hold hints",
  "Show a small Hold badge on keys with a long-press action",
  "Keyboard guide",
  "Hold Ctrl to switch between the regular keyboard and system keys",
  "Hold the language key to choose Steam, Alt + Shift, Ctrl + Shift, or Cmd + Space",
  "Use 1 ⇄ 2 to manually align the visible letters with the active system language",
  "After the first manual alignment, automatic swap follows each system language switch",
  "Keyboard position",
  "Press Menu, the right-side button opposite View, to move the keyboard between the top and bottom of the screen",
  "Swap primary and secondary keys",
  "Auto-swap after language switch",
  "After a system language shortcut, swap the primary and secondary key labels to stay synchronized",
  "Second layer only on QWERTY",
  "Hide secondary symbols on every other Steam keyboard layout, including layouts added later",
  "Plugin settings",
  "Developer mode",
  "Show diagnostic and experimental plugin tools",
  "Trackpad metrics",
  "Keep a low-overhead 15-minute live history plus three append-only 15-minute journal windows",
  "Stored only on this Steam Deck and never sent anywhere",
  "The journal appends every three minutes and immediately on suspicious pressure; manual captures remain until you delete them",
  "Live buffer",
  "Save current buffer",
  "Clear live buffer",
  "Saved captures",
  "Live",
  "No trackpad samples yet",
  "Delete capture",
  "Manual",
  "Collecting",
  "Stopped",
  "Device",
  "History",
  "Samples",
  "Pressure",
  "Touch",
  "Click",
  "Left",
  "Right",
  "Enable Developer mode to use trackpad diagnostics",
  "The live buffer was pinned as a saved capture",
]);

const russian = define([
  "Клавиатура",
  "Включить модуль клавиатуры",
  "Исправления и настройки виртуальной клавиатуры",
  "Клавиатура поверх окон",
  "Выводить клавиатуру Steam поверх окон приложений",
  "Не закрывать после Enter",
  "Оставлять клавиатуру открытой после нажатия Enter",
  "Системные клавиши по умолчанию",
  "Сразу показывать Ctrl, Fn, Esc, Delete и F1–F12; удерживайте кнопку предметов Steam для смены слоя",
  "Вторые подписи клавиш",
  "Показывать буквы из другой включённой раскладки Steam",
  "Вторая раскладка",
  "Автоматически выбирается включённая раскладка, которая сейчас не активна",
  "Автоматически",
  "Диагностика клавиатуры",
  "Записывать состояние клавиатуры и счётчики производительности в журнал Decky каждые пять секунд; отключается после перезапуска плагина",
  "Системное переключение языка",
  "Нажмите кнопку раскладки для смены языка; удерживайте её, чтобы выбрать сочетание или визуально поменять слои местами",
  "Сочетание для смены языка",
  "Бинды кнопок Steam Deck",
  "Использовать бамперы, триггеры, нажатия стиков или задние кнопки как клавиши, пока открыта виртуальная клавиатура",
  "Клавиша",
  "Быстрое действие",
  "Включить пользовательские сочетания на одну кнопку; корректное сочетание перекрывает обычный бинд",
  "Пример: Ctrl+Shift+Delete",
  "Некорректное сочетание — будет использован обычный бинд",
  "Второй набор хоткеев через R4",
  "Удерживайте R4 для второго набора быстрых действий; собственный бинд R4 будет перекрыт",
  "App Bridge",
  "Добавлять сторонние приложения в игровой режим через настраиваемые профили совместимости",
  "Быстрая настройка",
  "Добавить Parsec или исправить его ярлык Steam проверенным профилем с отслеживанием процесса",
  "Добавить / исправить Parsec",
  "Приложения",
  "Установленное приложение",
  "Обновить список приложений",
  "Название ярлыка",
  "Исполняемый файл",
  "Аргументы",
  "Рабочая папка",
  "Удерживать сессию Steam для процесса",
  "Очистить Steam preload",
  "Принудительное окружение Gamescope/X11",
  "Путь библиотек совместимости",
  "Добавить / исправить приложение",
  "Профиль и ярлык Steam готовы",
  "Добавить RustDesk или исправить его ярлык Steam профилем совместимости Gamescope/X11",
  "Добавить / исправить RustDesk",
  "Хоткеи",
  "Быстрые действия",
  "Подсказки удержания",
  "Показывать маленькую подпись Hold на клавишах с действием по удержанию",
  "Как пользоваться клавиатурой",
  "Удерживайте Ctrl, чтобы переключаться между обычной клавиатурой и системными клавишами",
  "Удерживайте кнопку языка, чтобы выбрать Steam, Alt + Shift, Ctrl + Shift или Cmd + Space",
  "Используйте 1 ⇄ 2, чтобы вручную совместить видимые буквы с активным системным языком",
  "После первой ручной синхронизации автосвап будет следовать за каждым системным переключением языка",
  "Положение клавиатуры",
  "Нажмите Menu — правую кнопку напротив View, чтобы перемещать клавиатуру между верхней и нижней частью экрана",
  "Поменять основные и вторые клавиши",
  "Автосвап после смены языка",
  "После системного переключения языка менять основные и вторые подписи местами для синхронизации",
  "Второй слой только на QWERTY",
  "Скрывать вторые символы на всех остальных раскладках клавиатуры Steam, включая добавленные позже",
  "Настройки плагина",
  "Режим разработчика",
  "Показывать диагностические и экспериментальные инструменты плагина",
  "Метрики трекпадов",
  "Хранить 15 минут живой истории и три append-only окна журнала по 15 минут с низкой нагрузкой",
  "Данные остаются только на этом Steam Deck и никуда не отправляются",
  "Журнал дописывается каждые три минуты и сразу при подозрительном давлении; ручные снимки хранятся, пока вы их не удалите",
  "Живой буфер",
  "Сохранить текущий буфер",
  "Очистить живой буфер",
  "Сохранённые снимки",
  "В реальном времени",
  "Данных трекпада пока нет",
  "Удалить снимок",
  "Ручной",
  "Сбор идёт",
  "Остановлено",
  "Устройство",
  "История",
  "События",
  "Давление",
  "Касание",
  "Клик",
  "Левый",
  "Правый",
  "Включите режим разработчика для диагностики трекпадов",
  "Живой буфер закреплён как сохранённый снимок",
  "Живой буфер в RAM будет очищен. Сохранённые снимки и append-only окна журнала не пострадают.",
  "Отмена",
  "Автоматический журнал",
  "Подтвердите изменение сбора метрик трекпадов. Кнопка подтверждения станет доступна через пять секунд.",
  "Подтвердить",
]);

const german = define([
  "Tastatur",
  "Tastaturmodul aktivieren",
  "Korrekturen und Anpassungen für die virtuelle Tastatur aktivieren",
  "Tastatur im Vordergrund",
  "Die Steam-Tastatur über Anwendungsfenstern anzeigen",
  "Nach Enter geöffnet lassen",
  "Die Tastatur nach dem Drücken von Enter nicht schließen",
  "Systemtasten standardmäßig",
  "Ctrl, Fn, Esc, Delete und F1–F12 sofort anzeigen; Steam-Objekttaste halten, um die Ebene zu wechseln",
  "Zweitbelegung anzeigen",
  "Buchstaben eines weiteren aktivierten Steam-Layouts anzeigen",
  "Zweites Layout",
  "Automatisch wählt ein aktiviertes, derzeit inaktives Layout",
  "Automatisch",
]);

const french = define([
  "Clavier",
  "Activer le module de clavier",
  "Activer les correctifs et la personnalisation du clavier virtuel",
  "Garder le clavier au premier plan",
  "Afficher le clavier Steam au-dessus des fenêtres d’application",
  "Garder ouvert après Entrée",
  "Ne pas fermer le clavier après avoir appuyé sur Entrée",
  "Touches système par défaut",
  "Afficher Ctrl, Fn, Échap, Suppr et F1–F12 à l’ouverture ; maintenir la touche des objets Steam pour changer de couche",
  "Libellés secondaires",
  "Afficher les lettres d’une autre disposition Steam activée",
  "Disposition secondaire",
  "Automatique choisit une disposition activée qui n’est pas utilisée",
  "Automatique",
]);

const spanish = define([
  "Teclado",
  "Activar módulo de teclado",
  "Activar correcciones y personalización del teclado virtual",
  "Mantener el teclado al frente",
  "Mostrar el teclado de Steam sobre las ventanas de aplicaciones",
  "Mantener abierto tras Intro",
  "No cerrar el teclado después de pulsar Intro",
  "Teclas del sistema por defecto",
  "Mostrar Ctrl, Fn, Esc, Supr y F1–F12 al abrir; mantén pulsada la tecla de objetos de Steam para cambiar de capa",
  "Etiquetas secundarias",
  "Mostrar letras de otra distribución de Steam activada",
  "Distribución secundaria",
  "Automático elige una distribución activada que no esté en uso",
  "Automático",
]);

const latam = define([
  "Teclado",
  "Activar módulo del teclado",
  "Activar correcciones y personalización del teclado virtual",
  "Mantener el teclado al frente",
  "Mostrar el teclado de Steam encima de las ventanas de aplicaciones",
  "Mantener abierto después de Enter",
  "No cerrar el teclado después de presionar Enter",
  "Teclas del sistema por defecto",
  "Mostrar Ctrl, Fn, Esc, Supr y F1–F12 al abrir; mantén presionada la tecla de objetos de Steam para cambiar de capa",
  "Etiquetas secundarias",
  "Mostrar letras de otra distribución de Steam habilitada",
  "Distribución secundaria",
  "Automático elige una distribución habilitada que no esté activa",
  "Automático",
]);

const italian = define([
  "Tastiera",
  "Attiva modulo tastiera",
  "Attiva correzioni e personalizzazioni della tastiera virtuale",
  "Mantieni la tastiera in primo piano",
  "Mostra la tastiera di Steam sopra le finestre delle applicazioni",
  "Mantieni aperta dopo Invio",
  "Non chiudere la tastiera dopo aver premuto Invio",
  "Tasti di sistema predefiniti",
  "Mostra Ctrl, Fn, Esc, Canc e F1–F12 all’apertura; tieni premuto il tasto oggetti di Steam per cambiare livello",
  "Etichette secondarie",
  "Mostra le lettere di un altro layout Steam attivo",
  "Layout secondario",
  "Automatico sceglie un layout attivo che non è attualmente in uso",
  "Automatico",
]);

const brazilian = define([
  "Teclado",
  "Ativar módulo do teclado",
  "Ativar correções e personalizações do teclado virtual",
  "Manter teclado em primeiro plano",
  "Exibir o teclado do Steam sobre as janelas dos aplicativos",
  "Manter aberto após Enter",
  "Não fechar o teclado após pressionar Enter",
  "Teclas do sistema por padrão",
  "Exibir Ctrl, Fn, Esc, Delete e F1–F12 ao abrir; segure a tecla de itens do Steam para trocar de camada",
  "Rótulos secundários",
  "Exibir letras de outro layout do Steam ativado",
  "Layout secundário",
  "Automático escolhe um layout ativado que não está em uso",
  "Automático",
]);

const portuguese = define([
  "Teclado",
  "Ativar módulo do teclado",
  "Ativar correções e personalização do teclado virtual",
  "Manter teclado em primeiro plano",
  "Mostrar o teclado do Steam sobre as janelas das aplicações",
  "Manter aberto após Enter",
  "Não fechar o teclado depois de premir Enter",
  "Teclas de sistema por predefinição",
  "Mostrar Ctrl, Fn, Esc, Delete e F1–F12 ao abrir; mantenha premida a tecla de itens do Steam para mudar de camada",
  "Etiquetas secundárias",
  "Mostrar letras de outra disposição do Steam ativada",
  "Disposição secundária",
  "Automático escolhe uma disposição ativada que não está em utilização",
  "Automático",
]);

const polish = define([
  "Klawiatura",
  "Włącz moduł klawiatury",
  "Włącz poprawki i dostosowanie klawiatury ekranowej",
  "Klawiatura zawsze na wierzchu",
  "Wyświetlaj klawiaturę Steam nad oknami aplikacji",
  "Pozostaw otwartą po Enter",
  "Nie zamykaj klawiatury po naciśnięciu Enter",
  "Domyślnie klawisze systemowe",
  "Pokazuj Ctrl, Fn, Esc, Delete i F1–F12 po otwarciu; przytrzymaj klawisz przedmiotów Steam, aby zmienić warstwę",
  "Dodatkowe oznaczenia klawiszy",
  "Pokazuj litery z innego włączonego układu Steam",
  "Dodatkowy układ",
  "Automatycznie wybiera włączony układ, który nie jest obecnie aktywny",
  "Automatycznie",
]);

const ukrainian = define([
  "Клавіатура",
  "Увімкнути модуль клавіатури",
  "Увімкнути виправлення та налаштування віртуальної клавіатури",
  "Клавіатура поверх вікон",
  "Показувати клавіатуру Steam поверх вікон програм",
  "Не закривати після Enter",
  "Залишати клавіатуру відкритою після натискання Enter",
  "Системні клавіші за замовчуванням",
  "Одразу показувати Ctrl, Fn, Esc, Delete і F1–F12; утримуйте клавішу предметів Steam для зміни шару",
  "Другі підписи клавіш",
  "Показувати літери з іншої ввімкненої розкладки Steam",
  "Друга розкладка",
  "Автоматично вибирається ввімкнена розкладка, яка зараз не активна",
  "Автоматично",
]);

const czech = define([
  "Klávesnice",
  "Povolit modul klávesnice",
  "Povolit opravy a úpravy virtuální klávesnice",
  "Klávesnice vždy navrchu",
  "Zobrazovat klávesnici Steam nad okny aplikací",
  "Ponechat otevřenou po Enteru",
  "Nezavírat klávesnici po stisknutí Enteru",
  "Systémové klávesy ve výchozím stavu",
  "Po otevření zobrazit Ctrl, Fn, Esc, Delete a F1–F12; podržením klávesy předmětů Steam přepnete vrstvu",
  "Sekundární popisky",
  "Zobrazovat písmena z jiného povoleného rozložení Steam",
  "Sekundární rozložení",
  "Automaticky vybere povolené rozložení, které právě není aktivní",
  "Automaticky",
]);

const dutch = define([
  "Toetsenbord",
  "Toetsenbordmodule inschakelen",
  "Correcties en aanpassingen voor het schermtoetsenbord inschakelen",
  "Toetsenbord op voorgrond houden",
  "Het Steam-toetsenbord boven toepassingsvensters tonen",
  "Open houden na Enter",
  "Het toetsenbord niet sluiten na Enter",
  "Standaard systeemtoetsen",
  "Ctrl, Fn, Esc, Delete en F1–F12 direct tonen; houd de Steam-itemtoets ingedrukt om van laag te wisselen",
  "Secundaire toetslabels",
  "Letters uit een andere ingeschakelde Steam-indeling tonen",
  "Secundaire indeling",
  "Automatisch kiest een ingeschakelde indeling die niet actief is",
  "Automatisch",
]);

const swedish = define([
  "Tangentbord",
  "Aktivera tangentbordsmodulen",
  "Aktivera korrigeringar och anpassningar för skärmtangentbordet",
  "Håll tangentbordet överst",
  "Visa Steam-tangentbordet ovanför programfönster",
  "Håll öppet efter Enter",
  "Stäng inte tangentbordet efter Enter",
  "Systemtangenter som standard",
  "Visa Ctrl, Fn, Esc, Delete och F1–F12 direkt; håll Steam-föremålstangenten för att byta lager",
  "Sekundära tangentetiketter",
  "Visa bokstäver från en annan aktiverad Steam-layout",
  "Sekundär layout",
  "Automatiskt väljer en aktiverad layout som inte används",
  "Automatiskt",
]);

const danish = define([
  "Tastatur",
  "Aktivér tastaturmodul",
  "Aktivér rettelser og tilpasning af skærmtastaturet",
  "Hold tastaturet øverst",
  "Vis Steam-tastaturet over programvinduer",
  "Hold åbent efter Enter",
  "Luk ikke tastaturet efter Enter",
  "Systemtaster som standard",
  "Vis Ctrl, Fn, Esc, Delete og F1–F12 ved åbning; hold Steam-genstandstasten nede for at skifte lag",
  "Sekundære tastemærkater",
  "Vis bogstaver fra et andet aktiveret Steam-layout",
  "Sekundært layout",
  "Automatisk vælger et aktiveret layout, som ikke er i brug",
  "Automatisk",
]);

const norwegian = define([
  "Tastatur",
  "Aktiver tastaturmodulen",
  "Aktiver rettelser og tilpasning av skjermtastaturet",
  "Hold tastaturet øverst",
  "Vis Steam-tastaturet over programvinduer",
  "Hold åpent etter Enter",
  "Ikke lukk tastaturet etter Enter",
  "Systemtaster som standard",
  "Vis Ctrl, Fn, Esc, Delete og F1–F12 ved åpning; hold Steam-gjenstandstasten for å bytte lag",
  "Sekundære tastemerker",
  "Vis bokstaver fra et annet aktivert Steam-oppsett",
  "Sekundært oppsett",
  "Automatisk velger et aktivert oppsett som ikke er i bruk",
  "Automatisk",
]);

const finnish = define([
  "Näppäimistö",
  "Ota näppäimistömoduuli käyttöön",
  "Ota virtuaalinäppäimistön korjaukset ja mukautukset käyttöön",
  "Pidä näppäimistö päällimmäisenä",
  "Näytä Steam-näppäimistö sovellusikkunoiden päällä",
  "Pidä avoinna Enterin jälkeen",
  "Älä sulje näppäimistöä Enterin painamisen jälkeen",
  "Järjestelmänäppäimet oletuksena",
  "Näytä Ctrl, Fn, Esc, Delete ja F1–F12 avattaessa; vaihda tasoa pitämällä Steam-esinenäppäintä painettuna",
  "Toissijaiset näppäinmerkinnät",
  "Näytä kirjaimet toisesta käytössä olevasta Steam-asettelusta",
  "Toissijainen asettelu",
  "Automaattinen valitsee käytössä olevan asettelun, joka ei ole aktiivinen",
  "Automaattinen",
]);

const romanian = define([
  "Tastatură",
  "Activează modulul tastaturii",
  "Activează remedierile și personalizarea tastaturii virtuale",
  "Menține tastatura în prim-plan",
  "Afișează tastatura Steam peste ferestrele aplicațiilor",
  "Menține deschisă după Enter",
  "Nu închide tastatura după apăsarea tastei Enter",
  "Taste de sistem în mod implicit",
  "Afișează Ctrl, Fn, Esc, Delete și F1–F12 la deschidere; ține apăsată tasta de obiecte Steam pentru a schimba stratul",
  "Etichete secundare",
  "Afișează litere din alt aranjament Steam activat",
  "Aranjament secundar",
  "Automat selectează un aranjament activat care nu este folosit",
  "Automat",
]);

const hungarian = define([
  "Billentyűzet",
  "Billentyűzetmodul engedélyezése",
  "A virtuális billentyűzet javításainak és testreszabásának engedélyezése",
  "Billentyűzet mindig felül",
  "A Steam billentyűzet megjelenítése az alkalmazásablakok felett",
  "Maradjon nyitva Enter után",
  "Ne zárja be a billentyűzetet az Enter megnyomása után",
  "Rendszerbillentyűk alapértelmezetten",
  "A Ctrl, Fn, Esc, Delete és F1–F12 azonnali megjelenítése; a rétegváltáshoz tartsa nyomva a Steam tárgygombot",
  "Másodlagos billentyűfeliratok",
  "Betűk megjelenítése egy másik engedélyezett Steam-kiosztásból",
  "Másodlagos kiosztás",
  "Az automatikus mód egy engedélyezett, jelenleg inaktív kiosztást választ",
  "Automatikus",
]);

const turkish = define([
  "Klavye",
  "Klavye modülünü etkinleştir",
  "Sanal klavye düzeltmelerini ve özelleştirmelerini etkinleştir",
  "Klavyeyi üstte tut",
  "Steam klavyesini uygulama pencerelerinin üzerinde göster",
  "Enter’dan sonra açık tut",
  "Enter’a bastıktan sonra klavyeyi kapatma",
  "Sistem tuşlarını varsayılan göster",
  "Açılışta Ctrl, Fn, Esc, Delete ve F1–F12’yi göster; katman değiştirmek için Steam öğeler tuşunu basılı tut",
  "İkincil tuş etiketleri",
  "Etkin başka bir Steam düzenindeki harfleri göster",
  "İkincil düzen",
  "Otomatik, o anda etkin olmayan bir düzeni seçer",
  "Otomatik",
]);

const greek = define([
  "Πληκτρολόγιο",
  "Ενεργοποίηση μονάδας πληκτρολογίου",
  "Ενεργοποίηση διορθώσεων και προσαρμογών του εικονικού πληκτρολογίου",
  "Πληκτρολόγιο πάντα μπροστά",
  "Εμφάνιση του πληκτρολογίου Steam πάνω από τα παράθυρα εφαρμογών",
  "Παραμονή ανοικτού μετά το Enter",
  "Να μην κλείνει το πληκτρολόγιο μετά το Enter",
  "Πλήκτρα συστήματος από προεπιλογή",
  "Εμφάνιση Ctrl, Fn, Esc, Delete και F1–F12 κατά το άνοιγμα· κρατήστε πατημένο το πλήκτρο αντικειμένων Steam για αλλαγή επιπέδου",
  "Δευτερεύουσες ετικέτες",
  "Εμφάνιση γραμμάτων από άλλη ενεργοποιημένη διάταξη Steam",
  "Δευτερεύουσα διάταξη",
  "Η αυτόματη επιλογή χρησιμοποιεί μια ενεργοποιημένη διάταξη που δεν είναι ενεργή",
  "Αυτόματα",
]);

const bulgarian = define([
  "Клавиатура",
  "Включване на модула за клавиатура",
  "Включване на поправките и настройките на виртуалната клавиатура",
  "Клавиатурата винаги отгоре",
  "Показване на Steam клавиатурата над прозорците на приложенията",
  "Оставяне отворена след Enter",
  "Клавиатурата да не се затваря след натискане на Enter",
  "Системни клавиши по подразбиране",
  "Показване на Ctrl, Fn, Esc, Delete и F1–F12 при отваряне; задръжте клавиша за Steam предмети за смяна на слоя",
  "Вторични надписи",
  "Показване на букви от друга включена Steam подредба",
  "Вторична подредба",
  "Автоматично избира включена подредба, която не е активна",
  "Автоматично",
]);

const arabic = define([
  "لوحة المفاتيح",
  "تفعيل وحدة لوحة المفاتيح",
  "تفعيل إصلاحات لوحة المفاتيح الافتراضية وتخصيصها",
  "إبقاء لوحة المفاتيح في المقدمة",
  "إظهار لوحة مفاتيح Steam فوق نوافذ التطبيقات",
  "إبقاؤها مفتوحة بعد Enter",
  "عدم إغلاق لوحة المفاتيح بعد الضغط على Enter",
  "مفاتيح النظام افتراضيًا",
  "إظهار Ctrl وFn وEsc وDelete وF1–F12 عند الفتح؛ اضغط مطولًا على مفتاح عناصر Steam لتبديل الطبقة",
  "تسميات المفاتيح الثانوية",
  "إظهار أحرف من تخطيط Steam مفعّل آخر",
  "التخطيط الثانوي",
  "يختار الوضع التلقائي تخطيطًا مفعّلًا غير نشط حاليًا",
  "تلقائي",
]);

const japanese = define([
  "キーボード",
  "キーボードモジュールを有効化",
  "仮想キーボードの修正とカスタマイズを有効にします",
  "キーボードを最前面に表示",
  "Steamキーボードをアプリのウィンドウより前に表示します",
  "Enter後も開いたままにする",
  "Enterを押した後もキーボードを閉じません",
  "システムキーを既定で表示",
  "起動時にCtrl、Fn、Esc、Delete、F1～F12を表示します。Steamアイテムキーの長押しでレイヤーを切り替えます",
  "セカンダリキーラベル",
  "有効な別のSteam配列の文字を表示します",
  "セカンダリ配列",
  "現在使用していない有効な配列を自動的に選択します",
  "自動",
]);

const koreana = define([
  "키보드",
  "키보드 모듈 활성화",
  "가상 키보드 수정 및 사용자 지정을 활성화합니다",
  "키보드를 항상 위에 표시",
  "Steam 키보드를 애플리케이션 창 위에 표시합니다",
  "Enter 후에도 열어 두기",
  "Enter를 누른 후 키보드를 닫지 않습니다",
  "시스템 키를 기본으로 표시",
  "열 때 Ctrl, Fn, Esc, Delete 및 F1–F12를 표시합니다. Steam 아이템 키를 길게 눌러 레이어를 전환합니다",
  "보조 키 레이블",
  "활성화된 다른 Steam 배열의 문자를 표시합니다",
  "보조 배열",
  "현재 활성화되지 않은 배열을 자동으로 선택합니다",
  "자동",
]);

const schinese = define([
  "键盘",
  "启用键盘模块",
  "启用虚拟键盘修复和自定义功能",
  "保持键盘置顶",
  "在应用程序窗口上方显示 Steam 键盘",
  "按 Enter 后保持打开",
  "按下 Enter 后不关闭键盘",
  "默认显示系统按键",
  "打开时显示 Ctrl、Fn、Esc、Delete 和 F1–F12；长按 Steam 物品键切换按键层",
  "辅助按键标签",
  "显示另一种已启用 Steam 布局中的字母",
  "辅助布局",
  "自动选择当前未激活的已启用布局",
  "自动",
]);

const tchinese = define([
  "鍵盤",
  "啟用鍵盤模組",
  "啟用虛擬鍵盤修正與自訂功能",
  "保持鍵盤置頂",
  "在應用程式視窗上方顯示 Steam 鍵盤",
  "按 Enter 後保持開啟",
  "按下 Enter 後不關閉鍵盤",
  "預設顯示系統按鍵",
  "開啟時顯示 Ctrl、Fn、Esc、Delete 與 F1–F12；長按 Steam 物品鍵切換按鍵層",
  "次要按鍵標籤",
  "顯示另一個已啟用 Steam 配置中的字母",
  "次要配置",
  "自動選擇目前未啟用的已啟用配置",
  "自動",
]);

const thai = define([
  "แป้นพิมพ์",
  "เปิดใช้โมดูลแป้นพิมพ์",
  "เปิดใช้การแก้ไขและการปรับแต่งแป้นพิมพ์เสมือน",
  "ให้แป้นพิมพ์อยู่ด้านบน",
  "แสดงแป้นพิมพ์ Steam เหนือหน้าต่างแอปพลิเคชัน",
  "เปิดค้างไว้หลัง Enter",
  "ไม่ปิดแป้นพิมพ์หลังจากกด Enter",
  "แสดงปุ่มระบบเป็นค่าเริ่มต้น",
  "แสดง Ctrl, Fn, Esc, Delete และ F1–F12 เมื่อเปิด; กดปุ่มไอเท็ม Steam ค้างไว้เพื่อสลับชั้น",
  "ป้ายปุ่มรอง",
  "แสดงตัวอักษรจากรูปแบบ Steam อื่นที่เปิดใช้อยู่",
  "รูปแบบรอง",
  "เลือกอัตโนมัติจากรูปแบบที่เปิดใช้แต่ไม่ได้ใช้งานอยู่",
  "อัตโนมัติ",
]);

const vietnamese = define([
  "Bàn phím",
  "Bật mô-đun bàn phím",
  "Bật các bản sửa lỗi và tùy chỉnh bàn phím ảo",
  "Giữ bàn phím ở trên cùng",
  "Hiển thị bàn phím Steam phía trên cửa sổ ứng dụng",
  "Giữ mở sau Enter",
  "Không đóng bàn phím sau khi nhấn Enter",
  "Hiển thị phím hệ thống mặc định",
  "Hiển thị Ctrl, Fn, Esc, Delete và F1–F12 khi mở; giữ phím vật phẩm Steam để đổi lớp",
  "Nhãn phím phụ",
  "Hiển thị chữ cái từ bố cục Steam đã bật khác",
  "Bố cục phụ",
  "Tự động chọn một bố cục đã bật nhưng hiện không hoạt động",
  "Tự động",
]);

const indonesian = define([
  "Papan ketik",
  "Aktifkan modul papan ketik",
  "Aktifkan perbaikan dan penyesuaian papan ketik virtual",
  "Pertahankan papan ketik di atas",
  "Tampilkan papan ketik Steam di atas jendela aplikasi",
  "Tetap buka setelah Enter",
  "Jangan tutup papan ketik setelah menekan Enter",
  "Tampilkan tombol sistem secara default",
  "Tampilkan Ctrl, Fn, Esc, Delete, dan F1–F12 saat dibuka; tahan tombol item Steam untuk mengganti lapisan",
  "Label tombol sekunder",
  "Tampilkan huruf dari tata letak Steam aktif lainnya",
  "Tata letak sekunder",
  "Otomatis memilih tata letak aktif yang sedang tidak digunakan",
  "Otomatis",
]);

const malay = define([
  "Papan kekunci",
  "Dayakan modul papan kekunci",
  "Dayakan pembaikan dan penyesuaian papan kekunci maya",
  "Kekalkan papan kekunci di atas",
  "Paparkan papan kekunci Steam di atas tetingkap aplikasi",
  "Kekalkan terbuka selepas Enter",
  "Jangan tutup papan kekunci selepas menekan Enter",
  "Paparkan kekunci sistem secara lalai",
  "Paparkan Ctrl, Fn, Esc, Delete dan F1–F12 semasa dibuka; tahan kekunci item Steam untuk menukar lapisan",
  "Label kekunci sekunder",
  "Paparkan huruf daripada susun atur Steam lain yang didayakan",
  "Susun atur sekunder",
  "Automatik memilih susun atur yang didayakan tetapi tidak aktif",
  "Automatik",
]);

const baseTranslations: Record<string, Strings> = {
  arabic,
  brazilian,
  bulgarian,
  czech,
  danish,
  dutch,
  english,
  finnish,
  french,
  german,
  greek,
  hungarian,
  indonesian,
  italian,
  japanese,
  koreana,
  latam,
  malay,
  norwegian,
  polish,
  portuguese,
  romanian,
  russian,
  sc_schinese: schinese,
  schinese,
  spanish,
  swedish,
  tchinese,
  thai,
  turkish,
  ukrainian,
  vietnamese,
};

export const translations: Record<string, Strings> = Object.fromEntries(
  Object.entries(baseTranslations).map(([language, strings]) => [
    language,
    {
      ...strings,
      ...(
        appBridgeTranslations[language]
        ?? (
          language === "sc_schinese"
            ? appBridgeTranslations.schinese
            : undefined
        )
      ),
      ...(
        systemToolsTranslations[language]
        ?? (
          language === "sc_schinese"
            ? systemToolsTranslations.schinese
            : undefined
        )
      ),
      ...(
        nestedDesktopTranslations[language]
        ?? (
          language === "sc_schinese"
            ? nestedDesktopTranslations.schinese
            : undefined
        )
      ),
    },
  ]),
);

import type { SecondaryLabelMap } from "./steamLayouts";
import {
  isSecondaryLabelRow,
  isSingleCharacter,
  isVisualSwapRow,
  selectSecondaryLabel,
} from "./layoutLabels";
import { resolveVisualKeyLabels } from "./visualKeyLabels";

const LABEL_CLASS = "fourdeus-secondary-label";
const KEY_CLASS = "fourdeus-secondary-label-key";
const SWAPPED_KEY_CLASS = "fourdeus-secondary-label-key-swapped";
const SWAPPED_NATIVE_LABEL_CLASS = "fourdeus-swapped-native-label";
const SWAPPED_PRIMARY_LABEL_CLASS = "fourdeus-swapped-primary-label";
const STYLE_ID = "fourdeus-secondary-label-style";
const LETTER_PATTERN = /^\p{L}$/u;
const SHIFT_BACKGROUND_VARIABLES = [
  "--key-toggleoneshot-background-color",
  "--key-toggleon-background-color",
];
const EMPTY_LABELS: readonly string[] = [];
const formatUpperCase = (label: string): string => label.toLocaleUpperCase();
const formatLowerCase = (label: string): string => label.toLocaleLowerCase();

interface ShiftClassCache {
  classes: string[];
  styleSheetCount: number;
}

const shiftClassesByDocument = new WeakMap<Document, ShiftClassCache>();

const isUpperCaseLetter = (value: string): boolean =>
  LETTER_PATTERN.test(value)
  && value === value.toLocaleUpperCase()
  && value !== value.toLocaleLowerCase();

const readStyleRules = (sheet: CSSStyleSheet): CSSStyleRule[] => {
  try {
    return Array.from(sheet.cssRules) as CSSStyleRule[];
  } catch {
    return [];
  }
};

const resolveShiftClasses = (document: Document): string[] => {
  const styleSheetCount = document.styleSheets.length;
  const cached = shiftClassesByDocument.get(document);
  if (cached?.styleSheetCount === styleSheetCount)
    return cached.classes;

  const classes = Array.from(document.styleSheets)
  .flatMap(readStyleRules)
  .filter((rule) =>
    SHIFT_BACKGROUND_VARIABLES.some((variable) =>
      rule.style?.getPropertyValue("background-color").includes(variable),
    ),
  )
  .flatMap((rule) =>
    rule.selectorText?.match(/^\.([A-Za-z0-9_-]+)$/)?.[1] ?? [],
  );
  shiftClassesByDocument.set(document, { classes, styleSheetCount });
  return classes;
};

const nativeCharacterSpans = (
  nativeKey: Element | null,
): HTMLElement[] => {
  if (!nativeKey)
    return [];

  const characters: HTMLElement[] = [];
  for (const span of nativeKey.querySelectorAll<HTMLElement>("span")) {
    const label = span.textContent?.trim();
    if (
      isSingleCharacter(label)
      && !span.classList.contains(LABEL_CLASS)
      && !span.classList.contains(SWAPPED_PRIMARY_LABEL_CLASS)
    ) {
      characters.push(span);
    }
  }
  return characters;
};

interface DisplayedSpan {
  opacity: number;
  span: HTMLElement;
}

const preferVisibleSpan = (
  ownerWindow: Window,
  displayed: DisplayedSpan | undefined,
  span: HTMLElement,
): DisplayedSpan | undefined => {
  const style = ownerWindow.getComputedStyle(span);
  if (style.display === "none" || style.visibility === "hidden")
    return displayed;
  const parsedOpacity = Number.parseFloat(style.opacity);
  const candidate = {
    opacity: Number.isFinite(parsedOpacity) ? parsedOpacity : 1,
    span,
  };
  return !displayed || candidate.opacity >= displayed.opacity
    ? candidate
    : displayed;
};

const displayedPrimarySpan = (
  key: HTMLElement,
  candidates = nativeCharacterSpans(key.firstElementChild),
): HTMLElement | undefined => {
  const ownerWindow = key.ownerDocument.defaultView;
  if (!ownerWindow)
    return undefined;
  if (candidates.length <= 1)
    return candidates[0];

  // Symbol keys can render active and inactive Shift labels together; opacity
  // identifies the active one without depending on hashed CSS class names.
  const displayed = candidates.reduce<DisplayedSpan | undefined>(
    (current, span) => preferVisibleSpan(ownerWindow, current, span),
    undefined,
  );
  return displayed?.span;
};

const displayedPrimary = (key: HTMLElement): string | undefined => {
  const span = displayedPrimarySpan(key);
  return span?.textContent?.trim()
    ?? key.dataset.key;
};

const clearNativeVisualSwap = (root: ParentNode): void => {
  root
    .querySelectorAll<HTMLElement>(`.${SWAPPED_NATIVE_LABEL_CLASS}`)
    .forEach((span) => span.classList.remove(SWAPPED_NATIVE_LABEL_CLASS));
  root
    .querySelectorAll<HTMLElement>(`.${SWAPPED_PRIMARY_LABEL_CLASS}`)
    .forEach((label) => label.remove());
};

const keyboardUsesUpperCase = (keys: HTMLElement[]): boolean => {
  const letterKey = keys.find(
    (key) => LETTER_PATTERN.test(key.dataset.key ?? ""),
  );
  return isUpperCaseLetter(letterKey ? displayedPrimary(letterKey) ?? "" : "");
};

const keyboardUsesShift = (keys: HTMLElement[]): boolean => {
  const shiftKey = keys.find(
    (key) => key.dataset.keyRow === "3" && key.dataset.keyCol === "0",
  );
  const nativeShift = shiftKey?.firstElementChild;
  const document = shiftKey?.ownerDocument;
  if (!nativeShift || !document)
    return false;

  return resolveShiftClasses(document).some(
    (className) => nativeShift.classList.contains(className),
  );
};

const secondaryText = (
  key: HTMLElement,
  labels: SecondaryLabelMap,
  shifted: boolean,
  formatLetter: (label: string) => string,
): string | undefined => {
  const row = key.dataset.keyRow;
  const column = key.dataset.keyCol;
  const variants = row !== undefined && column !== undefined
    ? labels.get(`${row}:${column}`)
    : undefined;
  const label = selectSecondaryLabel(
    variants?.normal,
    variants?.shifted,
    Number(row),
    shifted,
  );
  return label && LETTER_PATTERN.test(label) ? formatLetter(label) : label;
};

const ensureStyles = (document: Document): void => {
  if (document.getElementById(STYLE_ID))
    return;

  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .${KEY_CLASS} {
      position: relative !important;
    }

    .${LABEL_CLASS} {
      position: absolute;
      top: 4px;
      right: 6px;
      z-index: 2;
      color: inherit;
      opacity: 0.72;
      font-family: inherit;
      font-size: 13px;
      font-weight: 600;
      line-height: 1;
      pointer-events: none;
    }

    .${SWAPPED_NATIVE_LABEL_CLASS} {
      color: transparent !important;
      -webkit-text-fill-color: transparent !important;
      text-shadow: none !important;
    }

    .${SWAPPED_PRIMARY_LABEL_CLASS} {
      position: absolute;
      inset: 0;
      z-index: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      color: inherit !important;
      -webkit-text-fill-color: currentColor !important;
      opacity: 1 !important;
      pointer-events: none;
    }
  `;
  document.head.appendChild(style);
};

const nativePrimaryText = (
  key: HTMLElement,
  active: HTMLElement | undefined,
): string | undefined =>
  active?.textContent?.trim() ?? key.dataset.key;

const clearKeyLabels = (
  key: HTMLElement,
  secondaryLabel: HTMLElement | undefined,
): void => {
  if (!secondaryLabel && !key.classList.contains(KEY_CLASS))
    return;
  secondaryLabel?.remove();
  clearNativeVisualSwap(key);
  key.classList.remove(KEY_CLASS, SWAPPED_KEY_CLASS);
};

const copyNativeTypography = (
  source: HTMLElement,
  target: HTMLElement,
): void => {
  const ownerWindow = source.ownerDocument.defaultView;
  if (!ownerWindow)
    return;
  const style = ownerWindow.getComputedStyle(source);
  target.style.fontFamily = style.fontFamily;
  target.style.fontSize = style.fontSize;
  target.style.fontStyle = style.fontStyle;
  target.style.fontWeight = style.fontWeight;
  target.style.letterSpacing = style.letterSpacing;
  target.style.lineHeight = style.lineHeight;
  target.style.textTransform = style.textTransform;
};

const applyNativeVisualSwap = (
  key: HTMLElement,
  nativeKey: HTMLElement | null,
  active: HTMLElement | undefined,
  primary: string | undefined,
  replacement: string | undefined,
  swapped: boolean,
  nativeCharacters: readonly HTMLElement[],
): boolean => {
  if (!swapped || !active || !isSingleCharacter(primary)) {
    if (key.classList.contains(SWAPPED_KEY_CLASS)) {
      clearNativeVisualSwap(key);
      key.classList.remove(SWAPPED_KEY_CLASS);
    }
    return false;
  }

  key.classList.add(SWAPPED_KEY_CLASS);
  nativeCharacters.forEach((span) =>
    span.classList.add(SWAPPED_NATIVE_LABEL_CLASS));

  const existing = key.querySelector<HTMLElement>(
    `.${SWAPPED_PRIMARY_LABEL_CLASS}`,
  );
  if (existing) {
    if (existing.textContent !== replacement)
      existing.textContent = replacement ?? "";
    return true;
  }

  const visualPrimary = key.ownerDocument.createElement("span");
  visualPrimary.className = SWAPPED_PRIMARY_LABEL_CLASS;
  visualPrimary.textContent = replacement ?? "";
  visualPrimary.setAttribute("aria-hidden", "true");
  copyNativeTypography(active, visualPrimary);
  (nativeKey ?? key).appendChild(visualPrimary);
  return true;
};

const renderCornerLabel = (
  key: HTMLElement,
  nativeKey: HTMLElement | null,
  existing: HTMLElement | undefined,
  text: string,
): void => {
  if (existing) {
    if (existing.textContent !== text)
      existing.textContent = text;
    return;
  }

  const label = key.ownerDocument.createElement("span");
  label.className = LABEL_CLASS;
  label.textContent = text;
  label.setAttribute("aria-hidden", "true");
  (nativeKey ?? key).appendChild(label);
};

interface NativeLabelState {
  active?: HTMLElement;
  characters: HTMLElement[];
  nativeKey: HTMLElement | null;
  primary?: string;
  visibleLabels: readonly string[];
}

const readNativeLabelState = (
  key: HTMLElement,
  swapped: boolean,
): NativeLabelState => {
  const nativeKey = key.firstElementChild as HTMLElement | null;
  const numberRow = key.dataset.keyRow === "0";
  const characters = swapped || numberRow
    ? nativeCharacterSpans(nativeKey)
    : [];
  const active = swapped
    ? displayedPrimarySpan(key, characters)
    : undefined;
  return {
    active,
    characters,
    nativeKey,
    primary: swapped ? nativePrimaryText(key, active) : key.dataset.key,
    visibleLabels: numberRow
      ? characters.map((span) => span.textContent?.trim() ?? "")
      : EMPTY_LABELS,
  };
};

const renderKeyLabels = (
  key: HTMLElement,
  labels: SecondaryLabelMap,
  shifted: boolean,
  format: (label: string) => string,
  swapped: boolean,
): void => {
  const text = secondaryText(key, labels, shifted, format);
  if (!text && !key.classList.contains(KEY_CLASS))
    return;
  const native = readNativeLabelState(key, swapped);
  const visualLabels = resolveVisualKeyLabels(
    native.primary,
    text,
    swapped,
    native.visibleLabels,
  );
  const existing = native.nativeKey?.querySelector<HTMLElement>(
    `:scope > .${LABEL_CLASS}`,
  ) ?? key.querySelector<HTMLElement>(
    `:scope > .${LABEL_CLASS}`,
  ) ?? undefined;

  if (!visualLabels.secondary) {
    clearKeyLabels(key, existing);
    return;
  }

  key.classList.add(KEY_CLASS);
  const didSwap = applyNativeVisualSwap(
    key,
    native.nativeKey,
    native.active,
    native.primary,
    visualLabels.primary,
    swapped,
    native.characters,
  );
  renderCornerLabel(
    key,
    native.nativeKey,
    existing,
    (didSwap ? visualLabels.secondary : text) ?? "",
  );
};

export const renderSecondaryLabels = (
  keyboard: HTMLElement,
  labels: SecondaryLabelMap,
  swapped = false,
): void => {
  ensureStyles(keyboard.ownerDocument);

  const keys: HTMLElement[] = [];
  for (const key of keyboard.querySelectorAll<HTMLElement>(
    "div[data-key-row][data-key-col]",
  )) {
    if (isSecondaryLabelRow(Number(key.dataset.keyRow))) {
      keys.push(key);
    } else if (
        key.classList.contains(KEY_CLASS)
        || key.classList.contains(SWAPPED_KEY_CLASS)
    ) {
      clearKeyLabels(
        key,
        key.querySelector<HTMLElement>(`.${LABEL_CLASS}`) ?? undefined,
      );
    }
  }
  const format = keyboardUsesUpperCase(keys)
    ? formatUpperCase
    : formatLowerCase;
  const shifted = keyboardUsesShift(keys);

  keys.forEach((key) =>
    renderKeyLabels(
      key,
      labels,
      shifted,
      format,
      swapped && isVisualSwapRow(Number(key.dataset.keyRow)),
    ));
};

export const clearSecondaryLabels = (document: Document): void => {
  clearNativeVisualSwap(document);
  document
    .querySelectorAll(`.${LABEL_CLASS}`)
    .forEach((label) => label.remove());
  document
    .querySelectorAll(`.${KEY_CLASS}`)
    .forEach((key) => key.classList.remove(KEY_CLASS));
  document
    .querySelectorAll(`.${SWAPPED_KEY_CLASS}`)
    .forEach((key) => key.classList.remove(SWAPPED_KEY_CLASS));
  document.getElementById(STYLE_ID)?.remove();
};

import type { SecondaryLabelMap } from "./steamLayouts";
import { isSecondaryLabelRow } from "./layoutLabels";
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
const shiftClassesByDocument = new WeakMap<Document, string[]>();

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
  const cached = shiftClassesByDocument.get(document);
  if (cached)
    return cached;

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
  if (classes.length > 0)
    shiftClassesByDocument.set(document, classes);
  return classes;
};

const displayedPrimarySpan = (
  key: HTMLElement,
): HTMLElement | undefined => {
  const nativeKey = key.firstElementChild;
  const ownerWindow = key.ownerDocument.defaultView;
  if (!nativeKey || !ownerWindow)
    return undefined;

  const candidates = Array.from(
    nativeKey.querySelectorAll<HTMLElement>("span"),
  ).filter((span) => {
    const label = span.textContent?.trim();
    return Boolean(
      label
      && Array.from(label).length === 1
      && !span.classList.contains(LABEL_CLASS)
      && !span.classList.contains(SWAPPED_PRIMARY_LABEL_CLASS),
    );
  });
  if (candidates.length <= 1)
    return candidates[0];

  let displayed: { opacity: number; span: HTMLElement } | undefined;
  // Symbol keys can render active and inactive Shift labels together; opacity
  // identifies the active one without depending on hashed CSS class names.
  candidates.forEach((span) => {
    const style = ownerWindow.getComputedStyle(span);
    if (style.display === "none" || style.visibility === "hidden")
      return;

    const opacity = Number.parseFloat(style.opacity);
    const candidate = {
      opacity: Number.isFinite(opacity) ? opacity : 1,
      span,
    };
    if (!displayed || candidate.opacity >= displayed.opacity)
      displayed = candidate;
  });

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
  const label = shifted
    ? variants?.shifted ?? variants?.normal
    : variants?.normal;
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
): boolean => {
  if (!swapped || !active || !primary || Array.from(primary).length !== 1) {
    if (key.classList.contains(SWAPPED_KEY_CLASS)) {
      clearNativeVisualSwap(key);
      key.classList.remove(SWAPPED_KEY_CLASS);
    }
    return false;
  }

  key.classList.add(SWAPPED_KEY_CLASS);
  (nativeKey ?? key)
    .querySelectorAll<HTMLElement>("span")
    .forEach((span) => {
      const label = span.textContent?.trim();
      if (
        label
        && Array.from(label).length === 1
        && !span.classList.contains(LABEL_CLASS)
        && !span.classList.contains(SWAPPED_PRIMARY_LABEL_CLASS)
      ) {
        span.classList.add(SWAPPED_NATIVE_LABEL_CLASS);
      }
    });

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
  const active = swapped ? displayedPrimarySpan(key) : undefined;
  const primary = swapped
    ? nativePrimaryText(key, active)
    : key.dataset.key;
  const visualLabels = resolveVisualKeyLabels(primary, text, swapped);
  const nativeKey = key.firstElementChild as HTMLElement | null;
  const existing = nativeKey?.querySelector<HTMLElement>(
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
    nativeKey,
    active,
    primary,
    visualLabels.primary,
    swapped,
  );
  renderCornerLabel(
    key,
    nativeKey,
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

  const keys = Array.from(
    keyboard.querySelectorAll<HTMLElement>("div[data-key-row][data-key-col]"),
  ).filter((key) =>
    isSecondaryLabelRow(Number(key.dataset.keyRow)));
  const format = keyboardUsesUpperCase(keys)
    ? (label: string) => label.toLocaleUpperCase()
    : (label: string) => label.toLocaleLowerCase();
  const shifted = keyboardUsesShift(keys);

  keys.forEach((key) =>
    renderKeyLabels(key, labels, shifted, format, swapped));
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

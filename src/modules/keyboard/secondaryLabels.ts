import type { SecondaryLabelMap } from "./steamLayouts";

const LABEL_CLASS = "fourdeus-secondary-label";
const KEY_CLASS = "fourdeus-secondary-label-key";
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

const displayedPrimary = (key: HTMLElement): string | undefined => {
  const nativeKey = key.firstElementChild;
  const ownerWindow = key.ownerDocument.defaultView;
  if (!nativeKey || !ownerWindow)
    return key.dataset.key;

  let displayed: { label: string; opacity: number } | undefined;
  // Steam renders active and inactive Shift labels together; opacity identifies
  // the active one without depending on hashed CSS class names.
  nativeKey.querySelectorAll<HTMLElement>("span").forEach((span) => {
    if (span.classList.contains(LABEL_CLASS))
      return;
    const label = span.textContent?.trim();
    if (!label || Array.from(label).length !== 1)
      return;

    const style = ownerWindow.getComputedStyle(span);
    if (style.display === "none" || style.visibility === "hidden")
      return;

    const opacity = Number.parseFloat(style.opacity);
    const candidate = {
      label,
      opacity: Number.isFinite(opacity) ? opacity : 1,
    };
    if (!displayed || candidate.opacity >= displayed.opacity)
      displayed = candidate;
  });

  return displayed?.label ?? key.dataset.key;
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
  `;
  document.head.appendChild(style);
};

export const renderSecondaryLabels = (
  keyboard: HTMLElement,
  labels: SecondaryLabelMap,
): void => {
  ensureStyles(keyboard.ownerDocument);

  const keys = Array.from(
    keyboard.querySelectorAll<HTMLElement>("div[data-key-row][data-key-col]"),
  );
  const format = keyboardUsesUpperCase(keys)
    ? (label: string) => label.toLocaleUpperCase()
    : (label: string) => label.toLocaleLowerCase();
  const shifted = keyboardUsesShift(keys);

  keys.forEach((key) => {
    const text = secondaryText(key, labels, shifted, format);
    const primary = key.getAttribute("data-key");
    const nativeKey = key.firstElementChild as HTMLElement | null;
    const existing = nativeKey?.querySelector<HTMLElement>(
      `:scope > .${LABEL_CLASS}`,
    ) ?? key.querySelector<HTMLElement>(
      `:scope > .${LABEL_CLASS}`,
    );

    if (
      !text
      || text.toLocaleLowerCase() === primary?.toLocaleLowerCase()
    ) {
      existing?.remove();
      key.classList.remove(KEY_CLASS);
      return;
    }

    key.classList.add(KEY_CLASS);
    if (existing) {
      if (existing.textContent !== text)
        existing.textContent = text;
      return;
    }

    const label = keyboard.ownerDocument.createElement("span");
    label.className = LABEL_CLASS;
    label.textContent = text;
    label.setAttribute("aria-hidden", "true");
    (nativeKey ?? key).appendChild(label);
  });
};

export const clearSecondaryLabels = (document: Document): void => {
  document
    .querySelectorAll(`.${LABEL_CLASS}`)
    .forEach((label) => label.remove());
  document
    .querySelectorAll(`.${KEY_CLASS}`)
    .forEach((key) => key.classList.remove(KEY_CLASS));
  document.getElementById(STYLE_ID)?.remove();
};

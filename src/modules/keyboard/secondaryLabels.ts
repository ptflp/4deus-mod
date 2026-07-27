const LABEL_CLASS = "fourdeus-secondary-label";
const KEY_CLASS = "fourdeus-secondary-label-key";
const STYLE_ID = "fourdeus-secondary-label-style";
const LETTER_PATTERN = /^\p{L}$/u;

const isUpperCaseLetter = (value: string): boolean =>
  LETTER_PATTERN.test(value)
  && value === value.toLocaleUpperCase()
  && value !== value.toLocaleLowerCase();

const getDisplayedPrimaryLabel = (key: HTMLElement): string | undefined => {
  const nativeKey = key.firstElementChild;
  const ownerWindow = key.ownerDocument.defaultView;
  if (!nativeKey || !ownerWindow)
    return key.dataset.key;

  let displayed: { label: string; opacity: number } | undefined;
  nativeKey.querySelectorAll<HTMLElement>("span").forEach((span) => {
    const label = span.textContent?.trim();
    if (!label || !LETTER_PATTERN.test(label))
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

const matchPrimaryCase = (
  secondary: string,
  displayedPrimary: string | undefined,
): string => isUpperCaseLetter(displayedPrimary ?? "")
  ? secondary.toLocaleUpperCase()
  : secondary.toLocaleLowerCase();

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
      color: rgba(255, 255, 255, 0.72);
      font-family: inherit;
      font-size: 13px;
      font-weight: 600;
      line-height: 1;
      pointer-events: none;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.75);
    }
  `;
  document.head.appendChild(style);
};

export const renderSecondaryLabels = (
  keyboard: HTMLElement,
  labels: Map<string, string>,
): void => {
  ensureStyles(keyboard.ownerDocument);

  keyboard
    .querySelectorAll<HTMLElement>("div[data-key-row][data-key-col]")
    .forEach((key) => {
      const row = key.getAttribute("data-key-row");
      const column = key.getAttribute("data-key-col");
      const primary = key.getAttribute("data-key");
      const secondary = row !== null && column !== null
        ? labels.get(`${row}:${column}`)
        : undefined;
      const existing = key.querySelector<HTMLElement>(`:scope > .${LABEL_CLASS}`);
      const displayedSecondary = secondary
        ? matchPrimaryCase(secondary, getDisplayedPrimaryLabel(key))
        : undefined;

      if (!secondary || secondary.toLocaleLowerCase() === primary?.toLocaleLowerCase()) {
        existing?.remove();
        key.classList.remove(KEY_CLASS);
        return;
      }

      key.classList.add(KEY_CLASS);
      if (existing) {
        if (existing.textContent !== displayedSecondary)
          existing.textContent = displayedSecondary ?? secondary;
        return;
      }

      const label = keyboard.ownerDocument.createElement("span");
      label.className = LABEL_CLASS;
      label.textContent = displayedSecondary ?? secondary;
      label.setAttribute("aria-hidden", "true");
      key.appendChild(label);
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

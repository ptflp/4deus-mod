const LABEL_CLASS = "fourdeus-secondary-label";
const KEY_CLASS = "fourdeus-secondary-label-key";
const STYLE_ID = "fourdeus-secondary-label-style";

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

      if (!secondary || secondary.toLocaleLowerCase() === primary?.toLocaleLowerCase()) {
        existing?.remove();
        key.classList.remove(KEY_CLASS);
        return;
      }

      key.classList.add(KEY_CLASS);
      if (existing) {
        if (existing.textContent !== secondary)
          existing.textContent = secondary;
        return;
      }

      const label = keyboard.ownerDocument.createElement("span");
      label.className = LABEL_CLASS;
      label.textContent = secondary;
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

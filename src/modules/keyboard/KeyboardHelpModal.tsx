import {
  ConfirmModal,
  showModal,
} from "@decky/ui";
import {
  type ReactNode,
  useLayoutEffect,
  useRef,
} from "react";

import { useStrings } from "../../core/localization";
import { EMOJI_KEY, findNamedKey } from "./systemKeys";

interface KeyboardHelpModalProps {
  closeModal(): void;
  emojiGlyph?: Element;
}

interface HelpStepProps {
  badge: ReactNode;
  badgeIsCapsule?: boolean;
  description: string;
  title: string;
}

interface KeyboardHelpOptions {
  keyboard?: HTMLElement;
  onClosed?: () => void;
  parent?: EventTarget;
}

const SMILE_GLYPH_PLACEHOLDER = "☺";

const cloneEmojiGlyph = (
  keyboard: HTMLElement | undefined,
): Element | undefined => {
  const nativeKey = keyboard ? findNamedKey(keyboard, EMOJI_KEY) : null;
  const glyph = nativeKey?.firstElementChild?.querySelector("svg, img")
    ?? nativeKey?.querySelector("svg, img");
  return glyph?.cloneNode(true) as Element | undefined;
};

const NativeEmojiGlyph = ({ glyph }: { glyph?: Element }) => {
  const hostRef = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    const host = hostRef.current;
    if (!host || !glyph)
      return;
    const clone = host.ownerDocument.importNode(glyph, true);
    clone.setAttribute("aria-hidden", "true");
    clone.setAttribute("focusable", "false");
    clone.setAttribute("height", "16");
    clone.setAttribute("width", "16");
    clone.setAttribute(
      "style",
      "display:block;height:16px;width:16px;color:currentColor",
    );
    host.replaceChildren(clone);
    return () => host.replaceChildren();
  }, [glyph]);

  return (
    <span
      ref={hostRef}
      aria-hidden="true"
      style={{
        alignItems: "center",
        display: "inline-flex",
        height: "16px",
        justifyContent: "center",
        width: "16px",
      }}
    >
      {glyph ? null : SMILE_GLYPH_PLACEHOLDER}
    </span>
  );
};

const HoldEmojiBadge = ({
  glyph,
  label,
}: {
  glyph?: Element;
  label: string;
}) => {
  const parts = label.split(SMILE_GLYPH_PLACEHOLDER);
  return (
    <span
      style={{
        alignItems: "center",
        display: "inline-flex",
        gap: "2px",
        whiteSpace: "nowrap",
      }}
    >
      {parts.map((part, index) => (
        <span
          key={`${index}-${part}`}
          style={{
            alignItems: "center",
            display: "inline-flex",
            gap: "2px",
          }}
        >
          {part ? <span>{part}</span> : null}
          {index < parts.length - 1
            ? <NativeEmojiGlyph glyph={glyph} />
            : null}
        </span>
      ))}
    </span>
  );
};

const HelpStep = ({
  badge,
  badgeIsCapsule = false,
  description,
  title,
}: HelpStepProps) => (
  <div
    style={{
      alignItems: "center",
      background: "rgba(255, 255, 255, 0.055)",
      borderRadius: "8px",
      display: "grid",
      gap: "12px",
      gridTemplateColumns: "auto 1fr",
      padding: "10px 12px",
    }}
  >
    <span
      style={{
        alignItems: "center",
        border: "1px solid currentColor",
        borderRadius: badgeIsCapsule ? "999px" : "5px",
        display: "inline-flex",
        fontSize: "12px",
        fontWeight: 600,
        justifyContent: "center",
        lineHeight: 1,
        minWidth: "58px",
        padding: "5px 7px",
        textAlign: "center",
      }}
    >
      {badge}
    </span>
    <div>
      <div style={{ fontSize: "16px", fontWeight: 600 }}>{title}</div>
      <div style={{ fontSize: "13px", marginTop: "3px", opacity: 0.78 }}>
        {description}
      </div>
    </div>
  </div>
);

const MenuButtonGlyph = ({ label }: { label: string }) => (
  <span
    aria-label={label}
    role="img"
    style={{
      display: "inline-flex",
      flexDirection: "column",
      gap: "2px",
      width: "14px",
    }}
  >
    {[0, 1, 2].map((line) => (
      <span
        key={line}
        style={{
          background: "currentColor",
          borderRadius: "999px",
          height: "1.5px",
          width: "100%",
        }}
      />
    ))}
  </span>
);

const KeyboardHelpModal = ({
  closeModal,
  emojiGlyph,
}: KeyboardHelpModalProps) => {
  const strings = useStrings();
  return (
    <ConfirmModal
      bAlertDialog
      closeModal={closeModal}
      onOK={closeModal}
      strTitle={strings.keyboardHelpTitle}
      strOKButtonText={strings.ok}
      strDescription={(
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            minWidth: "540px",
          }}
        >
          <HelpStep
            badge={(
              <HoldEmojiBadge
                glyph={emojiGlyph}
                label={strings.keyboardHelpHoldCtrlBadge}
              />
            )}
            title={strings.systemKeyLayer}
            description={strings.keyboardHelpSystemLayerDescription}
          />
          <HelpStep
            badge={strings.keyboardHelpHoldLanguageBadge}
            title={strings.languageSwitchShortcut}
            description={strings.keyboardHelpLanguageMenuDescription}
          />
          <HelpStep
            badge="1 ⇄ 2"
            title={strings.swapKeys}
            description={strings.keyboardHelpSwapDescription}
          />
          <HelpStep
            badge={strings.keyboardHelpAutoBadge}
            title={strings.autoSwapVisualLayer}
            description={strings.keyboardHelpAutoSwapDescription}
          />
          <HelpStep
            badge={<MenuButtonGlyph label={strings.menuButton} />}
            badgeIsCapsule
            title={strings.keyboardHelpPosition}
            description={strings.keyboardHelpPositionDescription}
          />
        </div>
      )}
    />
  );
};

export const showKeyboardHelp = ({
  keyboard,
  onClosed,
  parent,
}: KeyboardHelpOptions): (() => void) => {
  let modal: ReturnType<typeof showModal> | undefined;
  let closed = false;
  const emojiGlyph = cloneEmojiGlyph(keyboard);
  const notifyClosed = (): void => {
    if (closed)
      return;
    closed = true;
    onClosed?.();
  };
  const close = (): void => {
    if (closed)
      return;
    modal?.Close();
    notifyClosed();
  };
  modal = showModal(
    <KeyboardHelpModal closeModal={close} emojiGlyph={emojiGlyph} />,
    parent,
    {
      bHideMainWindowForPopouts: false,
      bNeverPopOut: true,
      fnOnClose: notifyClosed,
      strTitle: "4deus Mod",
    },
  );
  return close;
};

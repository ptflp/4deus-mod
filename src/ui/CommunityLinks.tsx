import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
} from "@decky/ui";
import type { ReactNode } from "react";
import { FaDiscord, FaTelegramPlane } from "react-icons/fa";

import { COMMUNITY_LINKS } from "./communityLinks";

interface CommunityButtonProps {
  icon: ReactNode;
  label: string;
  url: string;
}

const CommunityButton = ({
  icon,
  label,
  url,
}: CommunityButtonProps) => (
  <PanelSectionRow>
    <ButtonItem
      layout="below"
      onClick={() => window.open(url, "_blank")}
    >
      <div
        style={{
          alignItems: "center",
          display: "flex",
          gap: "12px",
          padding: "2px",
          width: "100%",
        }}
      >
        <span
          style={{
            alignItems: "center",
            display: "flex",
            fontSize: "20px",
          }}
        >
          {icon}
        </span>
        <span style={{ flex: 1, fontSize: "15px" }}>{label}</span>
      </div>
    </ButtonItem>
  </PanelSectionRow>
);

export const CommunityLinks = () => (
  <PanelSection title="Discord · Telegram">
    <CommunityButton
      icon={<FaDiscord color="#5865F2" size={24} />}
      label={COMMUNITY_LINKS.discord.label}
      url={COMMUNITY_LINKS.discord.url}
    />
    <CommunityButton
      icon={<FaTelegramPlane color="#229ED9" size={24} />}
      label={COMMUNITY_LINKS.telegram.label}
      url={COMMUNITY_LINKS.telegram.url}
    />
  </PanelSection>
);

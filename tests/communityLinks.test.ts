import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { COMMUNITY_LINKS } from "../src/ui/communityLinks.ts";

test("community destinations remain stable", () => {
  assert.deepEqual(COMMUNITY_LINKS, {
    discord: {
      label: "Discord",
      url: "https://discord.gg/83eanusuRU",
    },
    github: {
      label: "GitHub",
      url: "https://github.com/ptflp",
    },
    telegram: {
      label: "Telegram",
      url: "https://t.me/the4deus",
    },
  });
});

test("README header exposes linked badges with text fallbacks", () => {
  const readme = readFileSync(
    new URL("../README.md", import.meta.url),
    "utf8",
  );
  const gettingStartedIndex = readme.indexOf("## Getting started");
  assert.notEqual(gettingStartedIndex, -1);
  const header = readme.slice(0, gettingStartedIndex);

  for (const { label, url } of Object.values(COMMUNITY_LINKS)) {
    assert.ok(
      header.includes(`[![${label} —`),
      `${label} badge needs visible fallback text`,
    );
    assert.ok(
      header.includes(`](${url})`),
      `${label} badge needs a clickable destination`,
    );
  }
});

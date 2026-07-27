import parser from "@typescript-eslint/parser";
import sonarjs from "eslint-plugin-sonarjs";

export default [{
  files: ["src/**/*.{ts,tsx}"],
  languageOptions: {
    parser,
    parserOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
    },
  },
  plugins: { sonarjs },
  rules: {
    "sonarjs/cognitive-complexity": ["error", 7],
  },
}];

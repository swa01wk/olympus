import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["app/**/*.{ts,tsx}", "components/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/lib/fixtures/**", "@/lib/fixtures"],
              message: "Import fixtures only via getServices() — see UI v2 isolation rules.",
            },
          ],
        },
      ],
    },
  },
  {
    files: [
      "lib/api/services.ts",
      "lib/events/fixture-stream.ts",
      "lib/fixtures/**",
      "tests/**",
    ],
    rules: {
      "no-restricted-imports": "off",
    },
  },
  {
    files: ["tests/e2e/**/*.ts"],
    rules: {
      "react-hooks/rules-of-hooks": "off",
      "no-restricted-properties": [
        "error",
        {
          object: "page",
          property: "waitForTimeout",
          message: "Use semantic waits (expect, expect.poll, data-checkpoint-id) instead of waitForTimeout.",
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;

import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// TMX-3614-lint baseline drift:
//   Loop 16 fixed the three real-bug rule classes (re-promoted to `error`):
//     - react-hooks/immutability      — auth.tsx hoist-before-declare resolved
//     - react-hooks/set-state-in-effect — TranslationWarehouse + landing fade-in resolved
//     - react/no-unescaped-entities   — 7 cosmetic cases escaped
//   Demoted rules (still under cleanup):
//     - @typescript-eslint/no-unused-vars  — 89 occurrences; sweep is TMX-3614-cleanup
//     - @typescript-eslint/no-explicit-any — 82 occurrences; typing migration is TMX-3614-types
//
// `--max-warnings 172` pins the new baseline. New code cannot add warnings.
// As the two follow-ups land, the cap drops in lockstep.
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Test artefacts:
    "playwright-report/**",
    "test-results/**",
  ]),
]);

export default eslintConfig;

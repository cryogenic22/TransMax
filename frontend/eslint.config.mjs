import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// TMX-3614 baseline: the legacy frontend tree carries 185 lint findings
// across these rule classes. The follow-up cleanup loop (TMX-3614-lint)
// drives them to zero. Until then they are demoted to warnings so CI can
// still gate against *new* ones via --max-warnings.
//
// Priority for TMX-3614-lint, hardest first:
//   1. react-hooks/immutability      — auth.tsx hoist-before-declare; real bug
//   2. react-hooks/set-state-in-effect — DocumentSegmentSelector + DashboardView; cascading renders
//   3. react/no-unescaped-entities   — design-system + DashboardView + JobsView; cosmetic
//   4. @typescript-eslint/no-unused-vars  — 89 occurrences; tree-shake or delete
//   5. @typescript-eslint/no-explicit-any — 82 occurrences; type the API client surface
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
      "react/no-unescaped-entities": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/immutability": "warn",
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

import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// TMX-3614-lint baseline drift:
//   Loop 16:  react-hooks/immutability + set-state-in-effect + no-unescaped-entities
//             back to `error` (real bugs fixed).
//   Loop 25:  @typescript-eslint/no-unused-vars back to `error` (89 → 0).
//             ^_ ignore-pattern enabled for intentional placeholders.
//   Loop 26:  @typescript-eslint/no-explicit-any 84 → 65 (catch-block sweep
//             via the new getErrMessage helper).
//   Loop 27 fire 1: 65 → 33. Every `any` outside lib/api.ts typed.
//   Loop 27 fire 2: 33 → 2. Every `Promise<any>` in lib/api.ts replaced
//             with a per-method response interface (Rule, Glossary,
//             GlossaryTerm, RuleAnalytics, RuleTestResult, ApiAck,
//             SegmentChangelogEntry, ToolAuditReport,
//             ToolBackTranslationResult, ToolMatrixResult,
//             ToolUniversalResult). no-explicit-any back to `error`.
//   Loop 27 fire 3: 2 → 0. The two react-hooks/exhaustive-deps warnings
//             (document/[docId] fetchDocData; workspace/upload
//             handleFileUpload) hoisted to useCallback with proper
//             dependency arrays. Lint is FULLY GREEN.
//
// All originally-demoted rules are now back to `error`. Cap = 0.
// New additions cannot land an unused-var, an `any`, an unescaped
// entity, a hoist-before-declare hook, a set-state-in-effect, or a
// missing-dep effect without breaking CI.
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
          destructuredArrayIgnorePattern: "^_",
        },
      ],
      "@typescript-eslint/no-explicit-any": "error",
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

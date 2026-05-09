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
//   Loop 27 fire 1: 65 → 33. Every `any` outside lib/api.ts is now typed —
//             tools (8), documents/[id] (6), workspace/page (2),
//             upload/page (3), jobs/page (3), review/[jobId] (2),
//             trust/page (1), knowledge/page (1), TopNavigation (1),
//             RichTextEditor (1), QualityDashboard (1), WorkspaceShell (2),
//             document/[docId] (1). The 31 residual all live in
//             lib/api.ts and need a deeper per-method response-type
//             refactor (TMX-3614-types-api).
//             Plus 2 react-hooks/exhaustive-deps warnings — pre-existing,
//             needs callback-hoist refactor.
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

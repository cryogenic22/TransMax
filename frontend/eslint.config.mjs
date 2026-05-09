import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// TMX-3614-lint baseline drift:
//   Loop 16:  react-hooks/immutability + set-state-in-effect + no-unescaped-entities
//             back to `error` (real bugs fixed).
//   Loop 25:  @typescript-eslint/no-unused-vars back to `error` (89 → 0).
//             ^_ ignore-pattern enabled for intentional placeholders.
//   Loop 26:  @typescript-eslint/no-explicit-any drives the residual 84 down.
//             Currently still `warn` until the typing migration completes.
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

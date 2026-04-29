---
description: "Frontend styling guardrails for the Next.js dashboard"
applyTo: "frontend/**/*"
---

- Treat [frontend/src/app/layout.tsx](frontend/src/app/layout.tsx) as the only place that imports [frontend/src/app/globals.css](frontend/src/app/globals.css); if CSS looks missing, inspect this file first.
- Keep new UI code under [frontend/src/](frontend/src/) so Tailwind can see it through the existing content globs in [frontend/tailwind.config.ts](frontend/tailwind.config.ts).
- Preserve the `@tailwind` directives, CSS variables, and body class contract in [frontend/src/app/globals.css](frontend/src/app/globals.css) and [frontend/src/app/layout.tsx](frontend/src/app/layout.tsx).
- When styles do not apply, verify the component is rendered inside the App Router shell and that the class names exist in files matched by the Tailwind config.
- Prefer fixing the root styling path or config mismatch before touching component markup.
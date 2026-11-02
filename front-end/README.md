# Front-end

React (Vite) single-page app with Chakra UI.

## Running npm

With the Docker stack up, `front-end/node_modules` is a mount point owned by root, so npm does not work
on your machine. Run it inside the container:

    docker compose exec web npm test
    docker compose exec web npm run lint
    docker compose exec web npm run build
    docker compose exec web npm audit
    docker compose exec web npm outdated

## Dependency audit

Last checked on 2 November 2026.

- `npm audit --omit=dev` (what ships to users): no known vulnerabilities.
- `npm audit` (including development tools): 6 moderate findings, all one problem: the `minimatch` library
  (denial of service with crafted file patterns) inside ESLint. It only runs on our own source files while
  linting, never in the app. ESLint 10 still depends on the vulnerable range, so upgrading does not help;
  it will be fixed when ESLint moves to `minimatch` 11. Re-check with `npm audit`.
- Not upgraded on purpose: Vite 8 with `@vitejs/plugin-react` 6 (a new bundler, needs its own change),
  and ESLint 10 with `eslint-plugin-react-hooks` 7 (the new rules flag existing code, such as setting
  state inside effects, and would need a code clean-up first).
- The Chakra UI command line (`@chakra-ui/cli`) was removed: nothing used it and it brought a vulnerable
  `zod`. To add Chakra UI snippets later, run `npx @chakra-ui/cli snippet add <name>`.

# Front-end tests

Run them inside the `web` container (running npm on the host does not work while
the compose stack is up, because `front-end/node_modules` is a root-owned mount):

    docker compose exec web npm test          # run once
    docker compose exec web npm run test:watch

CI runs `npm test` on every pull request (job **Front-end tests**).

## Stack

Vitest + jsdom, React Testing Library, `@testing-library/user-event` and
`jest-dom` matchers. Config lives in `vite.config.js` (`test` block).

## How tests are written

- **Behavior, not implementation.** Find things the way a user would: by role,
  label, placeholder or text. Assert on what the user sees and on the requests
  the page makes.
- **No real network.** `src/test/setup.js` replaces `fetch` with a function that
  fails; each test that needs the API calls `mockApi({ 'METHOD /path': body })`
  from `src/test/helpers.jsx` (a body, `[body, status]`, or a function returning a
  Promise). Requests that were not declared fail the test.
- **Fixed environment.** `VITE_API_URL` and `VITE_GOOGLE_CLIENT_ID` are set in
  `vite.config.js`, so a developer's own `.env` cannot change results. To test a
  missing variable use `vi.stubEnv(...)` and `vi.resetModules()`.
- **Fixed time.** For anything that depends on "today", use
  `vi.useFakeTimers({ toFake: ['Date'] })` and `vi.setSystemTime(...)` (only `Date`
  is faked, so waiting helpers keep working).
- **Rendering.** `renderApp(ui, { route })` wraps a component in the Chakra
  provider and a router, and adds a `data-testid="location"` element with the
  current route.
- **Google sign-in** is replaced by a stub button (`vi.mock('@react-oauth/google')`).
- Typing into the category box of the expense form needs a small delay between
  keys (`userEvent.setup({ delay: 20 })`), see TKT-32.
- Local storage is cleared before each test.

## Known bugs: skipped tests

When a test finds a bug that is not fixed in the same change, keep it, skip it
(`it.skip('TKT-<n>: what should happen', ...)`) and open a ticket that lists it.
Find them with:

    grep -rn "TKT-" front-end/src

Currently skipped: TKT-32 (money and error messages in the web app).

## Not covered yet

The chart components (`CategoryPieChart`, `ExpenseTrendLine`) draw with SVG
sizes that jsdom does not have, so they are only exercised through the
dashboard; the legacy `login` and `create-account` pages are not tested.

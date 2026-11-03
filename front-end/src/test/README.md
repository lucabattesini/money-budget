# Front-end tests

Run them inside the `web` container (running npm on the host does not work while
the compose stack is up, because `front-end/node_modules` is a root-owned mount):

    docker compose exec web npm test          # run once
    docker compose exec web npm run test:watch

CI runs `npm test` and a production build on every pull request (job
**Front-end tests**). The linter (`npm run lint`) runs in the **Lint** job together
with the back-end style checks.

## Stack

Vitest + jsdom, React Testing Library, `@testing-library/user-event` and
`jest-dom` matchers. Config lives in `vite.config.js` (`test` block).

## How tests are written

- **Behavior, not implementation.** Find things the way a user would: by role,
  label, placeholder or text. Assert on what the user sees and on the requests
  the page makes.
- **No real network, and no surprise requests.** `src/test/setup.js` replaces
  `fetch`; each test that needs the API calls `mockApi({ 'METHOD /path': body })`
  from `src/test/helpers.jsx` (a body, `[body, status]`, or a function returning a
  Promise). The app swallows network errors, so a request the test did not declare
  would otherwise go unnoticed: `afterEach` fails the test if there was one. To
  simulate the server being down on purpose, call `networkDown()`.
- **The family's currency and language are global** (`src/lib/locale.js`, one value for the whole app), so
  `setup.js` resets them to reais and Portuguese before every test. A test that needs another one calls
  `setLocale({ currency: 'USD', language: 'en' })` itself.
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
  keys (`userEvent.setup({ delay: 20 })`): that input is not controlled, so keys that
  arrive with no delay at all can be lost.
- Local storage is cleared before each test.
- **Testing a failure that changes nothing** (for example "must not say Salvo!"):
  the check must not run before the app has handled the response. Wait for a
  signal that only happens afterwards (the API client logs failures with
  `console.error`, so spy on it) and then `await act(async () => {})`.
- Assert order with `compareDocumentPosition` or by reading cards in order, not by
  `textContent.indexOf`; and make fixtures deliberately out of order so a list that
  is not sorted by the page cannot pass.

## Known bugs: skipped tests

When a test finds a bug that is not fixed in the same change, keep it, skip it
(`it.skip('TKT-<n>: what should happen', ...)`) and open a ticket that lists it.
Find them with:

    grep -rn "TKT-" front-end/src

Nothing is skipped at the moment.

## Not covered yet

The chart components (`CategoryPieChart`, `ExpenseTrendLine`) draw with SVG
sizes that jsdom does not have, so they are only exercised through the
dashboard; the legacy `login` and `create-account` pages are not tested.

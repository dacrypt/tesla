// Smoke test against the running app (cypress.config.ts baseUrl, `make dev`).
// The app either renders the dashboard tabs (no API key) or the sign-in screen.
describe('dashboard smoke', () => {
  it('loads the app shell', () => {
    cy.visit('/')
    cy.get('ion-tab-bar, input[aria-label="API key"]', { timeout: 15000 }).should('exist')
  })
})

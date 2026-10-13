import { useState } from 'react'

import type { AuthenticatedSession } from '@/api/client'
import { BrandMark } from '@/components/BrandMark'
import { PwaNotice } from '@/components/PwaNotice'

type AppShellProps = {
  user: AuthenticatedSession['user']
  sessionExpiresAt: string
  onSignOut: () => Promise<void>
}

type ShellPage = 'overview' | 'security'

export function AppShell({ user, sessionExpiresAt, onSignOut }: AppShellProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [activePage, setActivePage] = useState<ShellPage>('overview')
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const [signingOut, setSigningOut] = useState(false)

  async function handleSignOut() {
    setSignOutError(null)
    setSigningOut(true)
    try {
      await onSignOut()
    } catch (error) {
      setSignOutError(
        error instanceof Error
          ? error.message
          : 'Sign out could not be completed.',
      )
    } finally {
      setSigningOut(false)
    }
  }

  const roleSummary = user.roles.length
    ? user.roles.join(', ')
    : 'No operational role grants'
  const sessionExpiry = new Date(sessionExpiresAt)
  const hasValidExpiry = Number.isFinite(sessionExpiry.getTime())

  function selectPage(page: ShellPage) {
    setActivePage(page)
    setMenuOpen(false)
  }

  return (
    <div
      className="bg-canvas text-ink min-h-screen"
      onKeyDown={(event) => {
        if (event.key === 'Escape') setMenuOpen(false)
      }}
    >
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="border-line sticky top-0 z-30 flex h-[76px] items-center justify-between border-b bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <button
            aria-controls="primary-navigation"
            aria-expanded={menuOpen}
            aria-label={
              menuOpen ? 'Close navigation menu' : 'Open navigation menu'
            }
            className="menu-toggle"
            onClick={() => setMenuOpen((open) => !open)}
            type="button"
          >
            <span aria-hidden="true" className="menu-glyph">
              {menuOpen ? '×' : '☰'}
            </span>
          </button>
          <BrandMark compact />
          <div className="hidden sm:block">
            <p className="text-forest-900 text-sm font-bold">AGBOFA EduTrack</p>
            <p className="text-muted text-xs">Foundation workspace</p>
          </div>
        </div>
        <div className="flex items-center gap-3 sm:gap-5">
          <div className="hidden text-right sm:block">
            <p className="text-ink max-w-44 truncate text-sm font-medium">
              {user.displayName}
            </p>
            <p className="text-muted max-w-52 truncate text-xs">
              {roleSummary}
            </p>
          </div>
          <button
            className="button-quiet"
            disabled={signingOut}
            onClick={handleSignOut}
            type="button"
          >
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </header>

      <div className="mx-auto flex min-h-[calc(100vh-76px)] max-w-[1600px]">
        <aside
          className={`navigation-rail ${menuOpen ? 'navigation-rail-open' : ''}`}
          id="primary-navigation"
        >
          <nav aria-label="Primary navigation" className="space-y-2 p-4 lg:p-6">
            <a
              aria-current={activePage === 'overview' ? 'page' : undefined}
              className={`nav-link ${activePage === 'overview' ? 'nav-link-active' : ''}`}
              href="#main-content"
              onClick={() => selectPage('overview')}
            >
              <span aria-hidden="true" className="nav-indicator" />
              Overview
            </a>
            {user.isPrivileged && (
              <a
                aria-current={activePage === 'security' ? 'page' : undefined}
                className={`nav-link ${activePage === 'security' ? 'nav-link-active' : ''}`}
                href="#account-security"
                onClick={() => selectPage('security')}
              >
                <span aria-hidden="true" className="nav-indicator" />
                Account security
              </a>
            )}
          </nav>
          <div className="border-line hidden border-t p-6 lg:block">
            <p className="text-muted text-xs font-semibold tracking-[0.14em] uppercase">
              Access is enforced by the service
            </p>
            <p className="text-muted mt-2 text-xs leading-5">
              Navigation visibility is not a permission boundary. No school role
              or business permission is inferred by this shell.
            </p>
          </div>
        </aside>

        <main
          className="min-w-0 flex-1 px-4 py-8 sm:px-7 sm:py-10 lg:px-10"
          id="main-content"
        >
          <div className="mx-auto max-w-5xl">
            <PwaNotice />
            {signOutError && (
              <div className="alert-error mb-6" role="alert">
                {signOutError}
              </div>
            )}
            {activePage === 'security' && user.isPrivileged ? (
              <section
                aria-labelledby="account-security-title"
                id="account-security"
              >
                <p className="eyebrow">Account controls</p>
                <h1
                  className="text-ink mt-2 text-3xl font-bold tracking-tight sm:text-4xl"
                  id="account-security-title"
                >
                  Account security
                </h1>
                <p className="text-muted mt-4 max-w-3xl text-base leading-7">
                  This platform-privileged account requires an authenticator
                  factor. School role and recovery policies are not configured
                  by this foundation.
                </p>
                <dl className="surface-card mt-7 grid gap-5 sm:grid-cols-2">
                  <div>
                    <dt className="field-label">Multi-factor authentication</dt>
                    <dd className="text-ink text-sm font-semibold">
                      {user.mfaEnabled ? 'Enabled' : 'Required but not enabled'}
                    </dd>
                  </div>
                  <div>
                    <dt className="field-label">Platform access</dt>
                    <dd className="text-ink text-sm font-semibold">
                      {roleSummary}
                    </dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="field-label">
                      Current session maximum expiry
                    </dt>
                    <dd className="text-ink text-sm">
                      {hasValidExpiry ? (
                        <time dateTime={sessionExpiry.toISOString()}>
                          {sessionExpiry.toLocaleString()}
                        </time>
                      ) : (
                        'Not available'
                      )}
                    </dd>
                  </div>
                </dl>
                <p className="text-muted mt-5 text-sm leading-6">
                  Only this browser session can be ended here. Cross-device
                  session revocation and privileged-factor reset require a
                  separately approved identity lifecycle process.
                </p>
              </section>
            ) : (
              <>
                <div className="mb-8">
                  <p className="eyebrow">Foundation milestone</p>
                  <h1 className="text-ink mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
                    Your workspace is ready for the next approved stage.
                  </h1>
                  <p className="text-muted mt-4 max-w-3xl text-base leading-7">
                    This release establishes the application shell,
                    authentication, and engineering controls. School operations
                    are intentionally not represented here.
                  </p>
                </div>

                <section
                  aria-labelledby="scope-title"
                  className="bg-forest-900 shadow-card relative overflow-hidden rounded-3xl p-6 text-white sm:p-9"
                >
                  <div aria-hidden="true" className="hero-decoration" />
                  <div className="relative z-10 max-w-3xl">
                    <span className="text-forest-50 inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold tracking-wide">
                      No operational records in this milestone
                    </span>
                    <h2
                      id="scope-title"
                      className="mt-5 text-2xl font-bold sm:text-3xl"
                    >
                      Built for trustworthy school records.
                    </h2>
                    <p className="mt-3 max-w-2xl leading-7 text-white/80">
                      Learner, academic, reporting, intervention, and finance
                      modules remain outside this foundation milestone. No
                      simulated figures or sample learner records are shown.
                    </p>
                  </div>
                </section>

                <div className="mt-7 grid gap-5 md:grid-cols-2">
                  <section
                    className="surface-card"
                    aria-labelledby="foundation-title"
                  >
                    <div className="icon-tile" aria-hidden="true">
                      <span>01</span>
                    </div>
                    <h2
                      className="text-ink mt-5 text-lg font-bold"
                      id="foundation-title"
                    >
                      Access foundations
                    </h2>
                    <p className="text-muted mt-2 text-sm leading-6">
                      Sign-in uses server-managed sessions, CSRF protection, and
                      privileged-account MFA. Future permissions must be checked
                      server-side within an approved record scope.
                    </p>
                  </section>
                  <section
                    className="surface-card"
                    aria-labelledby="scope-next-title"
                  >
                    <div
                      className="icon-tile icon-tile-light"
                      aria-hidden="true"
                    >
                      <span>02</span>
                    </div>
                    <h2
                      className="text-ink mt-5 text-lg font-bold"
                      id="scope-next-title"
                    >
                      Deliberately limited
                    </h2>
                    <p className="text-muted mt-2 text-sm leading-6">
                      No academic policies, fees, learner information, payment
                      rails, or production records have been configured in this
                      release.
                    </p>
                  </section>
                </div>
                <footer className="border-line text-muted mt-9 border-t pt-5 text-xs leading-5">
                  AGBOFA EduTrack · Foundation only · This screen does not
                  report live school performance or financial status.
                </footer>
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

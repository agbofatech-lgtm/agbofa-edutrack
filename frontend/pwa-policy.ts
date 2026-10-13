/** Shared PWA cache boundaries used by Vite's Workbox configuration and tests. */
export const API_PATH_DENYLIST = /^\/api(?:\/|$)/

export const SHELL_PRECACHE_PATTERNS = [
  '**/*.{js,css,html,svg,png,webmanifest}',
] as const

/** The PWA foundation intentionally has no runtime API or authenticated-data cache. */
export const RUNTIME_CACHING_RULES: readonly never[] = []

export function isApiPath(pathname: string): boolean {
  return API_PATH_DENYLIST.test(pathname)
}

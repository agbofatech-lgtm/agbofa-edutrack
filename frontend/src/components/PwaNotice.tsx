import { useRegisterSW } from 'virtual:pwa-register/react'

export function PwaNotice() {
  const {
    offlineReady: [offlineReady, setOfflineReady],
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({ immediate: true })

  if (needRefresh) {
    return (
      <div className="alert-info mb-6" role="status">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p>An application update is ready to install.</p>
          <div className="flex gap-2">
            <button
              className="button-small-primary"
              onClick={() => updateServiceWorker(true)}
              type="button"
            >
              Reload to update
            </button>
            <button
              aria-label="Dismiss update notice"
              className="button-small-quiet"
              onClick={() => setNeedRefresh(false)}
              type="button"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (offlineReady) {
    return (
      <div className="alert-info mb-6" role="status">
        <div className="flex items-start justify-between gap-3">
          <p>
            The application shell is available offline. Account and school data
            still require a network connection.
          </p>
          <button
            aria-label="Dismiss offline-ready notice"
            className="button-small-quiet shrink-0"
            onClick={() => setOfflineReady(false)}
            type="button"
          >
            Dismiss
          </button>
        </div>
      </div>
    )
  }

  return null
}

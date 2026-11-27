import { useCallback, useEffect, useRef, useState } from 'react'

export type ViewState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'empty' }
  | { status: 'error'; message: string }

/** Mount/fetch lifecycle with abort: stale responses never overwrite newer ones. */
export function useAsync<T>(
  loader: (signal: AbortSignal) => Promise<T | null | undefined>,
  deps: readonly unknown[],
) {
  const [state, setState] = useState<ViewState<T>>({ status: 'idle' })
  const [cycle, setCycle] = useState(0)
  const runId = useRef(0)

  useEffect(() => {
    const id = ++runId.current
    const controller = new AbortController()
    setState((previous) => (previous.status === 'success' ? previous : { status: 'loading' }))
    loader(controller.signal).then(
      (data) => {
        if (runId.current !== id || controller.signal.aborted) return
        if (data == null || (Array.isArray(data) && data.length === 0)) {
          setState({ status: 'empty' })
        } else {
          setState({ status: 'success', data: data as T })
        }
      },
      (error: unknown) => {
        if (runId.current !== id || controller.signal.aborted) return
        setState({ status: 'error', message: errorMessage(error) })
      },
    )
    return () => controller.abort()
    // `loader` is re-created per render by callers; deps pin the cycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, cycle])

  const refresh = useCallback(() => setCycle((n) => n + 1), [])

  return { state, refresh }
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Something went wrong. Please retry.'
}

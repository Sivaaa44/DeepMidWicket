import { useCallback, useEffect, useState } from 'react'

/** Minimal pathname router: enough for "/" and "/admin" without a dependency. */
export function usePath() {
  const [path, setPath] = useState(() => window.location.pathname)
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const navigate = useCallback((to, { replace = false } = {}) => {
    if (to === window.location.pathname) return
    window.history[replace ? 'replaceState' : 'pushState']({}, '', to)
    setPath(to)
  }, [])
  return [path, navigate]
}

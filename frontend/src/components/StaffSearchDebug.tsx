import { useState } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import type { SearchDebugResponse } from '../types'

export default function StaffSearchDebug() {
  const { session } = useAuth()
  const token = session?.token ?? ''
  const [query, setQuery] = useState('Should I bring my HbA1c report?')
  const [result, setResult] = useState<SearchDebugResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function run(event?: React.FormEvent) {
    event?.preventDefault()
    if (!query.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.searchDebug(token, query.trim())
      setResult(response)
    } catch (caught) {
      setResult(null)
      setError(caught instanceof ApiError ? caught.message : 'Search debug failed.')
    } finally {
      setLoading(false)
    }
  }

  function group(title: string, chunks: SearchDebugResponse['keyword'], scoreLabel: string) {
    return (
      <div className="debug-group">
        <h4>{title} <span className="caveat">({scoreLabel})</span></h4>
        {chunks.length === 0 ? (
          <p className="caveat">No chunks.</p>
        ) : (
          <ul>
            {chunks.map((c) => (
              <li key={`${title}-${c.chunk_id}`}>
                <strong>{c.source} › {c.section}</strong> <span className="caveat">{c.chunk_id} · score {c.score ?? '—'} [{c.score_kind}]</span>
                <p className="caveat">{c.text}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  return (
    <section className="card debug-card" aria-label="Search debug">
      <h3>Search debug</h3>
      <form onSubmit={(e) => void run(e)} className="chat-form">
        <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Debug query" />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? 'Searching…' : 'Inspect retrieval'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="debug-columns">
          {group('Keyword', result.keyword, 'BM25 score')}
          {group('Vector', result.vector, 'vector similarity/distance')}
          {group('Hybrid', result.hybrid, 'hybrid fused score')}
        </div>
      )}
    </section>
  )
}

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Image as ImageIcon, Sparkles } from 'lucide-react'
import type { IllustrationSpec } from './types'

const API_BASE = (() => {
  const configured = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    return 'http://127.0.0.1:8002'
  }
  return ''
})()

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path
}

interface IllustrationResponse {
  imageUrl: string
  model: string
  aspectRatio: string
}

export function IllustrationCard({ spec, raw }: { spec?: IllustrationSpec; raw: string }) {
  const [imageUrl, setImageUrl] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!spec?.prompt) return
    let cancelled = false

    const run = async () => {
      setLoading(true)
      setError('')
      try {
        const response = await fetch(apiUrl('/api/illustrations'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: spec.prompt,
            style: spec.style,
            aspectRatio: spec.aspectRatio || '16:9',
          }),
        })
        const payload = await response.json().catch(() => ({})) as Partial<IllustrationResponse> & { detail?: string }
        if (!response.ok) {
          throw new Error(payload.detail || `Illustration request failed with status ${response.status}`)
        }
        if (!payload.imageUrl?.trim()) {
          throw new Error('Illustration request succeeded but returned no image.')
        }
        if (!cancelled) {
          setImageUrl(payload.imageUrl)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Illustration generation failed.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [spec?.aspectRatio, spec?.prompt, spec?.style])

  if (!spec?.prompt) {
    return (
      <div className="structured-card illustration-card">
        <div className="structured-card-header">
          <span className="structured-pill"><ImageIcon size={13} /> Illustration Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  return (
    <div className="structured-card illustration-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Sparkles size={13} /> AI Illustration</span>
        <h4>{spec.title || 'Concept Illustration'}</h4>
      </div>
      <div className="illustration-card-body">
        <div className="illustration-card-prompt">{spec.caption || spec.prompt}</div>
        {loading && (
          <div className="illustration-loading-shell">
            <motion.div
              className="illustration-loading-shimmer"
              initial={{ opacity: 0.45 }}
              animate={{ opacity: [0.45, 0.9, 0.45] }}
              transition={{ repeat: Infinity, duration: 1.6, ease: 'easeInOut' }}
            />
            <div className="illustration-loading-copy">Generating image…</div>
          </div>
        )}
        {!loading && imageUrl && (
          <motion.div
            className="illustration-media-wrap"
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
          >
            <img
              className="illustration-media"
              src={imageUrl}
              alt={spec.title || spec.prompt}
              onError={() => {
                setImageUrl('')
                setError('The generated image could not be displayed in the browser.')
              }}
            />
          </motion.div>
        )}
        {!loading && error && (
          <div className="illustration-error">
            <strong>Illustration unavailable</strong>
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  )
}

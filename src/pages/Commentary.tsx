import { useState, useEffect, useCallback } from 'react'
import type { CommentaryEntry, CommentarySearchResult, CommentarySource } from '../types'
import {
  getBooks, getChapters, getVerses, getCommentary,
  searchCommentary, getCommentarySources,
} from '../api/client'

const styles = {
  container: { maxWidth: 960, margin: '0 auto', padding: 16 },
  card: {
    background: '#161b22', border: '1px solid #30363d', borderRadius: 8,
    padding: 16, margin: '16px 0',
  },
  cardTitle: { fontSize: 18, color: '#58a6ff', margin: '0 0 12px 0' },
  label: { display: 'block', fontSize: 14, color: '#8b949e', margin: '8px 0 4px' },
  select: {
    width: '100%', padding: '10px 12px', borderRadius: 6, border: '1px solid #30363d',
    background: '#0d1117', color: '#e6edf3', fontSize: 15, outline: 'none',
    flex: 1,
  },
  inlineSelects: { display: 'flex', gap: 8 },
  checkboxRow: { display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0' },
  checkbox: { width: 'auto', margin: 0 },
  checkboxLabel: { fontSize: 14, color: '#8b949e', margin: 0 },
  btn: {
    padding: '10px 24px', borderRadius: 6, border: '1px solid #2ea043',
    background: '#238636', color: '#fff', fontWeight: 600, cursor: 'pointer',
    fontSize: 15, marginTop: 12,
  },
  btnSecondary: {
    padding: '10px 24px', borderRadius: 6, border: '1px solid #30363d',
    background: '#21262d', color: '#fff', fontWeight: 600, cursor: 'pointer',
    fontSize: 15,
  },
  tabs: { display: 'flex', borderBottom: '1px solid #30363d', marginBottom: 16 },
  tab: {
    padding: '10px 20px', cursor: 'pointer', fontSize: 15, color: '#8b949e',
    border: '1px solid transparent', borderBottom: 'none', borderRadius: '6px 6px 0 0',
    background: 'transparent', fontWeight: 500,
  },
  tabActive: { color: '#e6edf3', background: '#161b22', borderColor: '#30363d' },
  searchBox: { display: 'flex', gap: 8, marginBottom: 12 },
  searchInput: {
    flex: 1, padding: '10px 12px', borderRadius: 6, border: '1px solid #30363d',
    background: '#0d1117', color: '#e6edf3', fontSize: 15, outline: 'none',
    width: '100%',
  },
  table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: 14 },
  th: {
    padding: '12px 10px', textAlign: 'left' as const, borderBottom: '1px solid #21262d',
    color: '#8b949e', fontWeight: 500, position: 'sticky' as const, top: 0,
    background: '#161b22',
  },
  td: { padding: '12px 10px', textAlign: 'left' as const, borderBottom: '1px solid #21262d' },
  empty: { textAlign: 'center' as const, padding: 40, color: '#8b949e' },
  toast: {
    position: 'fixed' as const, top: 16, right: 16, padding: '12px 20px',
    borderRadius: 6, fontSize: 15, zIndex: 100,
  },
  commentaryItem: {
    padding: 16, background: '#0d1117', border: '1px solid #21262d',
    borderRadius: 6, marginBottom: 10,
  },
  sourceName: { fontSize: 14, color: '#58a6ff', marginBottom: 4 },
  reference: { fontSize: 14, color: '#8b949e', marginBottom: 6 },
  text: { fontSize: 16, lineHeight: 1.7, color: '#c9d1d9' },
  chunks: { fontSize: 12, color: '#7ee787', marginLeft: 4 },
  resultCount: { marginBottom: 8, fontSize: 14, color: '#8b949e' },
}

function Toast({ msg, type, onDone }: { msg: string; type: 'ok' | 'err'; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 3000)
    return () => clearTimeout(t)
  }, [onDone])
  const bg = type === 'ok' ? '#238636' : '#da3633'
  return <div style={{ ...styles.toast, background: bg, color: '#fff' }}>{msg}</div>
}

export default function Commentary() {
  const [books, setBooks] = useState<string[]>([])
  const [chapters, setChapters] = useState<number[]>([])
  const [verses, setVerses] = useState<number[]>([])
  const [selectedBook, setSelectedBook] = useState('')
  const [selectedChapter, setSelectedChapter] = useState('')
  const [selectedVerse, setSelectedVerse] = useState('')
  const [includeStudyLight, setIncludeStudyLight] = useState(true)
  const [commentaryResults, setCommentaryResults] = useState<CommentaryEntry[] | null>(null)
  const [loadingCommentary, setLoadingCommentary] = useState(false)

  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<CommentarySearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)

  const [sources, setSources] = useState<CommentarySource[]>([])
  const [loadingSources, setLoadingSources] = useState(true)

  const [activeTab, setActiveTab] = useState<'browse' | 'search'>('browse')
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null)
  const showToast = useCallback((msg: string, type: 'ok' | 'err') => setToast({ msg, type }), [])

  useEffect(() => {
    getBooks().then(setBooks).catch(() => showToast('Failed to load books', 'err'))
  }, [showToast])

  useEffect(() => {
    getCommentarySources()
      .then(data => { setSources(data); setLoadingSources(false) })
      .catch(() => { showToast('Failed to load sources', 'err'); setLoadingSources(false) })
  }, [showToast])

  useEffect(() => {
    if (!selectedBook) {
      setChapters([]); setSelectedChapter(''); setSelectedVerse(''); setVerses([])
      return
    }
    setChapters([]); setSelectedChapter(''); setSelectedVerse(''); setVerses([])
    getChapters(selectedBook).then(setChapters).catch(() => showToast('Failed to load chapters', 'err'))
  }, [selectedBook, showToast])

  useEffect(() => {
    if (!selectedBook || !selectedChapter) {
      setVerses([]); setSelectedVerse(''); return
    }
    setVerses([]); setSelectedVerse('')
    getVerses(selectedBook, parseInt(selectedChapter))
      .then(setVerses)
      .catch(() => showToast('Failed to load verses', 'err'))
  }, [selectedBook, selectedChapter, showToast])

  async function loadCommentaries() {
    if (!selectedBook || !selectedChapter || !selectedVerse) return
    setLoadingCommentary(true)
    setCommentaryResults(null)
    try {
      const data = await getCommentary(selectedBook, parseInt(selectedChapter), parseInt(selectedVerse), includeStudyLight)
      setCommentaryResults(data)
    } catch (e: unknown) {
      showToast(`Error: ${e instanceof Error ? e.message : 'Unknown'}`, 'err')
    }
    setLoadingCommentary(false)
  }

  function handleVerseChange(value: string) {
    setSelectedVerse(value)
    if (value && selectedBook && selectedChapter) {
      setLoadingCommentary(true)
      setCommentaryResults(null)
      getCommentary(selectedBook, parseInt(selectedChapter), parseInt(value), includeStudyLight)
        .then(setCommentaryResults)
        .catch(() => showToast('Failed to load commentary', 'err'))
        .finally(() => setLoadingCommentary(false))
    }
  }

  async function handleSearch() {
    const q = searchQuery.trim()
    if (!q) return
    setSearching(true)
    setSearchResults(null)
    try {
      const data = await searchCommentary(q)
      setSearchResults(data)
    } catch (e: unknown) {
      showToast(`Search error: ${e instanceof Error ? e.message : 'Unknown'}`, 'err')
    }
    setSearching(false)
  }

  function handleSearchKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter') handleSearch()
  }

  return (
    <div style={styles.container}>
      {toast && <Toast msg={toast.msg} type={toast.type} onDone={() => setToast(null)} />}

      <div style={styles.card}>
        <div style={styles.tabs}>
          <div
            style={{ ...styles.tab, ...(activeTab === 'browse' ? styles.tabActive : {}) }}
            onClick={() => setActiveTab('browse')}
          >
            Browse
          </div>
          <div
            style={{ ...styles.tab, ...(activeTab === 'search' ? styles.tabActive : {}) }}
            onClick={() => setActiveTab('search')}
          >
            Search
          </div>
        </div>

        {activeTab === 'browse' && (
          <div>
            <h2 style={styles.cardTitle}>Browse by Verse</h2>
            <div style={styles.inlineSelects}>
              <select
                style={styles.select}
                value={selectedBook}
                onChange={e => setSelectedBook(e.target.value)}
              >
                <option value="">— Book —</option>
                {books.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
              <select
                style={styles.select}
                value={selectedChapter}
                onChange={e => setSelectedChapter(e.target.value)}
                disabled={!selectedBook || chapters.length === 0}
              >
                <option value="">Chapter</option>
                {chapters.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <select
                style={styles.select}
                value={selectedVerse}
                onChange={e => handleVerseChange(e.target.value)}
                disabled={!selectedChapter || verses.length === 0}
              >
                <option value="">Verse</option>
                {verses.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div style={styles.checkboxRow}>
              <input
                type="checkbox"
                id="studylightToggle"
                checked={includeStudyLight}
                onChange={e => setIncludeStudyLight(e.target.checked)}
                style={styles.checkbox}
              />
              <label htmlFor="studylightToggle" style={styles.checkboxLabel}>Include StudyLight.org commentaries</label>
            </div>
            <button
              style={styles.btn}
              onClick={loadCommentaries}
              disabled={!selectedBook || !selectedChapter || !selectedVerse || loadingCommentary}
            >
              {loadingCommentary ? 'Loading...' : 'Load Commentaries'}
            </button>
            <div style={{ marginTop: 16 }}>
              {loadingCommentary && <div style={styles.empty}>Loading...</div>}
              {!loadingCommentary && commentaryResults !== null && commentaryResults.length === 0 && (
                <div style={styles.empty}>No commentaries found for this verse.</div>
              )}
              {!loadingCommentary && commentaryResults !== null && commentaryResults.length > 0 && (
                <>
                  <div style={styles.resultCount}>
                    {commentaryResults.length} result{commentaryResults.length > 1 ? 's' : ''} for {selectedBook} {selectedChapter}:{selectedVerse}
                  </div>
                  {commentaryResults.map((item, i) => {
                    const sourceName = item.source_name || item.source || 'Commentary'
                    const ref = item.reference || (item.book_code ? `${item.book_code} ${item.chapter}:${item.verse}` : '')
                    const text = item.commentary_text || item.chunk_text || ''
                    return (
                      <div key={item.id || i} style={styles.commentaryItem}>
                        <div style={styles.sourceName}>{sourceName}</div>
                        {ref && <div style={styles.reference}>{ref}</div>}
                        <div style={styles.text}>{text}</div>
                      </div>
                    )
                  })}
                </>
              )}
            </div>
          </div>
        )}

        {activeTab === 'search' && (
          <div>
            <h2 style={styles.cardTitle}>Search Commentaries</h2>
            <div style={styles.searchBox}>
              <input
                style={styles.searchInput}
                type="text"
                placeholder="Search all commentary content..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={handleSearchKey}
                autoComplete="off"
              />
              <button style={styles.btnSecondary} onClick={handleSearch} disabled={searching}>
                {searching ? 'Searching...' : 'Search'}
              </button>
            </div>
            <div>
              {searching && <div style={styles.empty}>Searching...</div>}
              {!searching && searchResults !== null && searchResults.length === 0 && (
                <div style={styles.empty}>No results found.</div>
              )}
              {!searching && searchResults !== null && searchResults.length > 0 && (
                <>
                  <div style={styles.resultCount}>
                    {searchResults.length} result{searchResults.length > 1 ? 's' : ''}
                  </div>
                  {searchResults.map((res, i) => (
                    <div key={res.rowid || i} style={styles.commentaryItem}>
                      <div style={styles.sourceName}>{res.source_name || 'Commentary'}</div>
                      {res.reference && <div style={styles.reference}>{res.reference}</div>}
                      <div style={styles.text}>{res.chunk_text || ''}</div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}
      </div>

      <div style={styles.card}>
        <h2 style={styles.cardTitle}>Commentary Sources</h2>
        {loadingSources ? (
          <div style={styles.empty}>Loading...</div>
        ) : sources.length === 0 ? (
          <div style={styles.empty}>No sources found.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Abbreviation</th>
                  <th style={styles.th}>Name</th>
                  <th style={styles.th}>Verse Count</th>
                </tr>
              </thead>
              <tbody>
                {sources.map(s => (
                  <tr key={s.abbr}>
                    <td style={styles.td}><span style={{ color: '#79c0ff', fontFamily: 'monospace', fontSize: 12 }}>{s.abbr}</span></td>
                    <td style={styles.td}>{s.name}</td>
                    <td style={styles.td}><span style={{ color: '#7ee787', fontFamily: 'monospace', fontSize: 12 }}>{s.chunk_count}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

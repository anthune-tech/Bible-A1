import { useEffect, useRef, useState, useCallback } from 'react'
import { getBooks, getChapters, getVerses, queryVerse, getCommentary, askAI } from '../api/client'
import { useChat } from '../ChatContext'
import type { QueryResult, VerseData, CommentaryEntry } from '../types'

const OT_BOOKS = new Set([
  "Gen","Exod","Lev","Num","Deut","Josh","Judg","Ruth","1Sam","2Sam","1Kgs","2Kgs",
  "1Chr","2Chr","Ezra","Neh","Esth","Job","Ps","Prov","Eccl","Song","Isa","Jer","Lam",
  "Ezek","Dan","Hos","Joel","Amos","Obad","Jonah","Mic","Nah","Hab","Zeph","Hag","Zech","Mal",
])

const BOOK_LINKS: Record<string, string> = {
  Gen: "https://www.studylight.org/commentary/genesis.html",
  Exod: "https://www.studylight.org/commentary/exodus.html",
  Lev: "https://www.studylight.org/commentary/leviticus.html",
  Num: "https://www.studylight.org/commentary/numbers.html",
  Deut: "https://www.studylight.org/commentary/deuteronomy.html",
  Josh: "https://www.studylight.org/commentary/joshua.html",
  Judg: "https://www.studylight.org/commentary/judges.html",
  Ruth: "https://www.studylight.org/commentary/ruth.html",
  "1Sam": "https://www.studylight.org/commentary/1-samuel.html",
  "2Sam": "https://www.studylight.org/commentary/2-samuel.html",
  "1Kgs": "https://www.studylight.org/commentary/1-kings.html",
  "2Kgs": "https://www.studylight.org/commentary/2-kings.html",
  "1Chr": "https://www.studylight.org/commentary/1-chronicles.html",
  "2Chr": "https://www.studylight.org/commentary/2-chronicles.html",
  Ezra: "https://www.studylight.org/commentary/ezra.html",
  Neh: "https://www.studylight.org/commentary/nehemiah.html",
  Esth: "https://www.studylight.org/commentary/esther.html",
  Job: "https://www.studylight.org/commentary/job.html",
  Ps: "https://www.studylight.org/commentary/psalms.html",
  Prov: "https://www.studylight.org/commentary/proverbs.html",
  Eccl: "https://www.studylight.org/commentary/ecclesiastes.html",
  Song: "https://www.studylight.org/commentary/songofsongs.html",
  Isa: "https://www.studylight.org/commentary/isaiah.html",
  Jer: "https://www.studylight.org/commentary/jeremiah.html",
  Lam: "https://www.studylight.org/commentary/lamentations.html",
  Ezek: "https://www.studylight.org/commentary/ezekiel.html",
  Dan: "https://www.studylight.org/commentary/daniel.html",
  Hos: "https://www.studylight.org/commentary/hosea.html",
  Joel: "https://www.studylight.org/commentary/joel.html",
  Amos: "https://www.studylight.org/commentary/amos.html",
  Obad: "https://www.studylight.org/commentary/obadiah.html",
  Jonah: "https://www.studylight.org/commentary/jonah.html",
  Mic: "https://www.studylight.org/commentary/micah.html",
  Nah: "https://www.studylight.org/commentary/nahum.html",
  Hab: "https://www.studylight.org/commentary/habakkuk.html",
  Zeph: "https://www.studylight.org/commentary/zephaniah.html",
  Hag: "https://www.studylight.org/commentary/haggai.html",
  Zech: "https://www.studylight.org/commentary/zechariah.html",
  Mal: "https://www.studylight.org/commentary/malachi.html",
  Matt: "https://www.studylight.org/commentary/matthew.html",
  Mark: "https://www.studylight.org/commentary/mark.html",
  Luke: "https://www.studylight.org/commentary/luke.html",
  John: "https://www.studylight.org/commentary/john.html",
  Acts: "https://www.studylight.org/commentary/acts.html",
  Rom: "https://www.studylight.org/commentary/romans.html",
  "1Cor": "https://www.studylight.org/commentary/1-corinthians.html",
  "2Cor": "https://www.studylight.org/commentary/2-corinthians.html",
  Gal: "https://www.studylight.org/commentary/galatians.html",
  Eph: "https://www.studylight.org/commentary/ephesians.html",
  Phil: "https://www.studylight.org/commentary/philippians.html",
  Col: "https://www.studylight.org/commentary/colossians.html",
  "1Thess": "https://www.studylight.org/commentary/1-thessalonians.html",
  "2Thess": "https://www.studylight.org/commentary/2-thessalonians.html",
  "1Tim": "https://www.studylight.org/commentary/1-timothy.html",
  "2Tim": "https://www.studylight.org/commentary/2-timothy.html",
  Titus: "https://www.studylight.org/commentary/titus.html",
  Phlm: "https://www.studylight.org/commentary/philemon.html",
  Heb: "https://www.studylight.org/commentary/hebrews.html",
  Jas: "https://www.studylight.org/commentary/james.html",
  "1Pet": "https://www.studylight.org/commentary/1-peter.html",
  "2Pet": "https://www.studylight.org/commentary/2-peter.html",
  "1John": "https://www.studylight.org/commentary/1-john.html",
  "2John": "https://www.studylight.org/commentary/2-john.html",
  "3John": "https://www.studylight.org/commentary/3-john.html",
  Jude: "https://www.studylight.org/commentary/jude.html",
  Rev: "https://www.studylight.org/commentary/revelation.html",
}

function parseHash(): { book: string; chapter: number; verse: number } | null {
  const m = window.location.hash.match(/^#(\w+?)\.(\d+)\.(\d+)$/)
  if (!m) return null
  return { book: m[1], chapter: parseInt(m[2]), verse: parseInt(m[3]) }
}

function fmtHash(book: string, ch: number, vs: number) {
  return `#${book}.${ch}.${vs}`
}

const BOOK_ABBREV: Record<string, string> = {
  Genesis: "Gen", Exodus: "Exod", Leviticus: "Lev", Numbers: "Num",
  Deuteronomy: "Deut", Joshua: "Josh", Judges: "Judg", Ruth: "Ruth",
  "1 Samuel": "1Sam", "2 Samuel": "2Sam", "1 Kings": "1Kgs", "2 Kings": "2Kgs",
  "1 Chronicles": "1Chr", "2 Chronicles": "2Chr", Ezra: "Ezra", Nehemiah: "Neh",
  Esther: "Esth", Job: "Job", Psalm: "Ps", Psalms: "Ps",
  Proverbs: "Prov", Ecclesiastes: "Eccl", "Song of Solomon": "Song",
  "Song of Songs": "Song", Isaiah: "Isa", Jeremiah: "Jer",
  Lamentations: "Lam", Ezekiel: "Ezek", Daniel: "Dan", Hosea: "Hos",
  Joel: "Joel", Amos: "Amos", Obadiah: "Obad", Jonah: "Jonah",
  Micah: "Mic", Nahum: "Nah", Habakkuk: "Hab", Zephaniah: "Zeph",
  Haggai: "Hag", Zechariah: "Zech", Malachi: "Mal",
  Matthew: "Matt", Mark: "Mark", Luke: "Luke", John: "John",
  Acts: "Acts", Romans: "Rom", "1 Corinthians": "1Cor", "2 Corinthians": "2Cor",
  Galatians: "Gal", Ephesians: "Eph", Philippians: "Phil", Colossians: "Col",
  "1 Thessalonians": "1Thess", "2 Thessalonians": "2Thess",
  "1 Timothy": "1Tim", "2 Timothy": "2Tim", Titus: "Titus",
  Philemon: "Phlm", Hebrews: "Heb", James: "Jas",
  "1 Peter": "1Pet", "2 Peter": "2Pet", "1 John": "1John",
  "2 John": "2John", "3 John": "3John", Jude: "Jude",
  Revelation: "Rev",
  Gen: "Gen", Exod: "Exod", Lev: "Lev", Num: "Num", Deut: "Deut",
  Josh: "Josh", Judg: "Judg",
  "1Sam": "1Sam", "2Sam": "2Sam", "1Kgs": "1Kgs", "2Kgs": "2Kgs",
  "1Chr": "1Chr", "2Chr": "2Chr", Neh: "Neh",
  Esth: "Esth", Ps: "Ps", Prov: "Prov", Eccl: "Eccl",
  Song: "Song", Isa: "Isa", Jer: "Jer", Lam: "Lam", Ezek: "Ezek",
  Dan: "Dan", Hos: "Hos", Obad: "Obad", Mic: "Mic", Nah: "Nah", Hab: "Hab", Zeph: "Zeph",
  Hag: "Hag", Zech: "Zech", Mal: "Mal",
  Matt: "Matt", Rom: "Rom", "1Cor": "1Cor", "2Cor": "2Cor",
  Gal: "Gal", Eph: "Eph", Phil: "Phil", Col: "Col",
  "1Thess": "1Thess", "2Thess": "2Thess", "1Tim": "1Tim", "2Tim": "2Tim",
  Phlm: "Phlm", Heb: "Heb", Jas: "Jas",
  "1Pet": "1Pet", "2Pet": "2Pet", "1John": "1John",
  "2John": "2John", "3John": "3John", Rev: "Rev",
  Kejadian: "Gen", Keluaran: "Exod", Imamat: "Lev", Bilangan: "Num",
  Ulangan: "Deut", Yosua: "Josh", "Hakim-hakim": "Judg", Rut: "Ruth",
  "1 Raja-raja": "1Kgs", "2 Raja-raja": "2Kgs",
  "1 Tawarikh": "1Chr", "2 Tawarikh": "2Chr",
  Nehemia: "Neh", Ester: "Esth", Ayub: "Job",
  Mazmur: "Ps", Amsal: "Prov", Pengkhotbah: "Eccl",
  "Kidung Agung": "Song", Yesaya: "Isa", Yeremia: "Jer",
  Ratapan: "Lam", Yehezkiel: "Ezek",
  Yoel: "Joel", Obaja: "Obad",
  Yunus: "Jonah", Mikha: "Mic",
  Habakuk: "Hab", Zefanya: "Zeph", Hagai: "Hag",
  Zakharia: "Zech", Maleakhi: "Mal",
  Matius: "Matt", Markus: "Mark", Lukas: "Luke", Yohanes: "John",
  "Kisah Para Rasul": "Acts", Roma: "Rom",
  "1 Korintus": "1Cor", "2 Korintus": "2Cor",
  Galatia: "Gal", Efesus: "Eph", Filipi: "Phil", Kolose: "Col",
  "1 Tesalonika": "1Thess", "2 Tesalonika": "2Thess",
  "1 Timotius": "1Tim", "2 Timotius": "2Tim",
  Filemon: "Phlm", Ibrani: "Heb", Yakobus: "Jas",
  "1 Petrus": "1Pet", "2 Petrus": "2Pet",
  "1 Yohanes": "1John", "2 Yohanes": "2John", "3 Yohanes": "3John",
  Yudas: "Jude", Wahyu: "Rev",
}

const BOOK_NAMES = Object.keys(BOOK_ABBREV).sort((a, b) => b.length - a.length)
const BOOK_PATTERN = BOOK_NAMES.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
const BOOK_ABBREV_LC: Record<string, string> = {}
for (const [k, v] of Object.entries(BOOK_ABBREV)) BOOK_ABBREV_LC[k.toLowerCase()] = v

const sidebar = {
  flexBasis: '20%',
  minWidth: 220,
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 16,
  display: 'flex',
  flexDirection: 'column' as const,
  gap: 10,
  position: 'sticky' as const,
  top: 68,
  maxHeight: 'calc(100vh - 84px)',
  overflowY: 'auto' as const,
}

export default function BibleViewer() {
  const [books, setBooks] = useState<string[]>([])
  const [chapters, setChapters] = useState<number[]>([])
  const [verses, setVerses] = useState<number[]>([])
  const [book, setBook] = useState('')
  const [chapter, setChapter] = useState(0)
  const [verse, setVerse] = useState(0)
  const [version, setVersion] = useState('kjv')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [commentaryLoading, setCommentaryLoading] = useState(false)
  const [commentary, setCommentary] = useState<CommentaryEntry[]>([])
  const { entries, addEntry, loading: chatLoading, setLoading: setChatLoading, currentQuestion: chatQuestion, setCurrentQuestion: setChatQuestion } = useChat()
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null)
  const chatRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getBooks().then(setBooks)
  }, [])

  const loadFromHash = useCallback(() => {
    const h = parseHash()
    if (h && books.includes(h.book)) {
      setBook(h.book)
      getChapters(h.book).then(chs => {
        setChapters(chs)
        if (chs.includes(h.chapter)) {
          setChapter(h.chapter)
          getVerses(h.book, h.chapter).then(vs => {
            setVerses(vs)
            if (vs.includes(h.verse)) {
              setVerse(h.verse)
            }
          })
        }
      })
    }
  }, [books])

  useEffect(() => { loadFromHash() }, [loadFromHash])

  useEffect(() => {
    window.addEventListener('hashchange', loadFromHash)
    return () => window.removeEventListener('hashchange', loadFromHash)
  }, [loadFromHash])

  useEffect(() => {
    if (!book) return
    setChapter(0); setVerse(0); setResult(null); setCommentary([])
    getChapters(book).then(setChapters)
  }, [book])

  useEffect(() => {
    if (!book || !chapter) return
    setVerse(0); setResult(null); setCommentary([])
    getVerses(book, chapter).then(setVerses)
  }, [book, chapter])

  useEffect(() => {
    if (!book || !chapter || !verse) return
    loadVerse(book, chapter, verse)
  }, [book, chapter, verse, version])

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight
  }, [entries])

  useEffect(() => {
    if (toast) setTimeout(() => setToast(null), 3000)
  }, [toast])

  const loadVerse = useCallback(async (b: string, ch: number, vs: number) => {
    setLoading(true)
    window.location.hash = fmtHash(b, ch, vs)
    try {
      const [qr, comm] = await Promise.all([
        queryVerse(b, ch, vs, vs, version),
        (() => { setCommentaryLoading(true); return getCommentary(b, ch, vs, true) })(),
      ])
      setResult(qr)
      setCommentary(comm)
      setCommentaryLoading(false)
    } catch (e: any) {
      setToast({ msg: `Error: ${e.message}`, type: 'err' })
    }
    setLoading(false)
  }, [version])

  const escHtml = (s: string) => {
    const d = document.createElement('div')
    d.textContent = s
    return d.innerHTML
  }

  const renderInterlinear = (vd: VerseData) => {
    if (!vd.text) return null
    const isOt = OT_BOOKS.has(book)
    const strongRe = /([^\[\]]+?)\[((G|H)(\d+))\](?:\(([^)]*)\))?/g

    let enHtml = vd.text
    enHtml = enHtml.replace(strongRe, (_, word, strong) => {
      return `<a href="#" onclick="event.preventDefault(); window.dispatchEvent(new CustomEvent('strong-popup', {detail:{strong:'${strong}'}}))" style="color:var(--strong-color);text-decoration:none;cursor:pointer;border-bottom:1px dashed var(--strong-color)" title="${strong}">${escHtml(word.trim())}</a>`
    })
    enHtml = enHtml.replace(/\n/g, '<br>')

    return (
      <div key={vd.verse} style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 15, color: 'var(--text-secondary)', marginBottom: 4 }}>
          {vd.reference}
        </div>

        {isOt && vd.interlinear.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>Hebrew (BHS) with Strong's</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {vd.interlinear.map((iw, idx) => (
                <div key={idx} style={{
                  textAlign: 'center', minWidth: 48, padding: '6px 8px',
                  background: 'var(--interlinear-bg)', borderRadius: 4, border: '1px solid var(--interlinear-border)',
                }}>
                  <div style={{ fontSize: 24, color: 'var(--text)', fontFamily: 'var(--hebrew-font)', lineHeight: 1.3 }}>
                    {iw.original || '־'}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                    {iw.transliteration || '…'}
                  </div>
                  <div style={{ fontSize: 14, color: 'var(--success)' }}>
                    <span style={{ borderBottom: '1px dashed var(--success)', cursor: 'pointer' }}
                      title={`Strong's ${iw.strong}: ${iw.gloss}`}>
                      {iw.gloss || '…'}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {iw.strong}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {!isOt && vd.interlinear.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>
              Greek (TR) with Strong's
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {vd.interlinear.map((iw, idx) => (
                <div key={idx} style={{
                  textAlign: 'center', minWidth: 48, padding: '6px 8px',
                  background: 'var(--interlinear-bg)', borderRadius: 4, border: '1px solid var(--interlinear-border)',
                }}>
                  <div style={{ fontSize: 24, color: 'var(--text)', fontFamily: 'var(--greek-font)', lineHeight: 1.3 }}>
                    {iw.original || '…'}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                    {iw.transliteration || '…'}
                  </div>
                  {iw.grammar && (
                    <div style={{ fontSize: 12, color: '#d29922' }}>{iw.grammar}</div>
                  )}
                  <div style={{ fontSize: 14, color: 'var(--success)' }}>
                    <span style={{ borderBottom: '1px dashed var(--success)', cursor: 'pointer' }}
                      title={`Strong's ${iw.strong}: ${iw.gloss}`}>
                      {iw.gloss || '…'}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{iw.strong}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ fontSize: 19, lineHeight: 1.8, color: 'var(--text)' }}
          dangerouslySetInnerHTML={{ __html: enHtml }} />
      </div>
    )
  }

  const handleAsk = async () => {
    const q = chatQuestion.trim()
    if (!q) return
    setChatLoading(true)
    setChatQuestion('')
    const context = result?.verses.map(v => `${v.reference}: ${v.text}`).join('\n') || ''
    try {
      const res = await askAI(q, context)
      addEntry(q, res.answer)
    } catch (e: any) {
      addEntry(q, `Error: ${e.message}`)
    }
    setChatLoading(false)
  }

  function renderChatAnswer(text: string) {
    if (!text) return null
    const parts: React.ReactNode[] = []
    let lastIndex = 0, found = false
    const re = new RegExp(`(?<!\\w)(${BOOK_PATTERN})\\s+(\\d+):(\\d+)(?:[–-](\\d+))?(?!\\w)`, 'gi')
    let match: RegExpExecArray | null
    while ((match = re.exec(text)) !== null) {
      found = true
      if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index))
      const bookName = match[1], ch = parseInt(match[2], 10), vs = parseInt(match[3], 10)
      const abbrev = BOOK_ABBREV_LC[bookName.toLowerCase()]
      if (abbrev) {
        parts.push(<a key={match.index} href={fmtHash(abbrev, ch, vs)}
          style={{ color: 'var(--accent)', textDecoration: 'underline', cursor: 'pointer' }}>{match[0]}</a>)
      } else {
        parts.push(match[0])
      }
      lastIndex = re.lastIndex
    }
    if (!found) return text
    if (lastIndex < text.length) parts.push(text.slice(lastIndex))
    return <>{parts}</>
  }

  const copyCitation = () => {
    if (!result) return
    const text = result.verses.map(v => `${v.reference}: ${v.text.replace(/\[G\d+\]/g, '').replace(/\[H\d+\]/g, '').trim()}`).join('\n')
    navigator.clipboard.writeText(text).then(() => {
      setToast({ msg: 'Copied to clipboard', type: 'ok' })
    })
  }

  return (
    <div style={{
      width: '100%', padding: '16px 16px',
      display: 'flex', gap: 16, alignItems: 'flex-start',
    }}>
      {toast && (
        <div className={`toast show ${toast.type}`}>{toast.msg}</div>
      )}

      {/* Left sidebar — Navigation */}
      <div style={sidebar}>
        <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--accent)', marginBottom: 4 }}>Navigation</div>

        <select value={book} onChange={e => setBook(e.target.value)} style={{ width: '100%' }}>
          <option value="">— Book —</option>
          <optgroup label="Old Testament">
            {books.filter(b => OT_BOOKS.has(b)).map(b => <option key={b} value={b} style={{color:'#e8837a'}}>{b}</option>)}
          </optgroup>
          <optgroup label="New Testament">
            {books.filter(b => !OT_BOOKS.has(b)).map(b => <option key={b} value={b} style={{color:'#7ab8e8'}}>{b}</option>)}
          </optgroup>
        </select>

        <select value={chapter || ''} onChange={e => setChapter(Number(e.target.value))} disabled={!book} style={{ width: '100%' }}>
          <option value="">Chapter</option>
          {chapters.map(c => <option key={c} value={c}>{c}</option>)}
        </select>

        <select value={verse || ''} onChange={e => setVerse(Number(e.target.value))} disabled={!chapter} style={{ width: '100%' }}>
          <option value="">Verse</option>
          {verses.map(v => <option key={v} value={v}>{v}</option>)}
        </select>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ display: 'flex', gap: 6, fontSize: 15, margin: 0, cursor: 'pointer', flexDirection: 'column', alignItems: 'stretch' }}>
            <select value={version} onChange={e => setVersion(e.target.value)}
              style={{ width: '100%', fontSize: 14 }}>
              <option value="kjv">KJV (King James)</option>
              <option value="tb">TB (Terjemahan Baru)</option>
              <option value="nlt">NLT (New Living Translation)</option>
            </select>
          </label>
        </div>

        {result && (
          <>
            <div style={{ display: 'flex', gap: 4 }}>
              <button className="secondary" style={{ flex: 1, padding: '8px 8px', fontSize: 14 }} onClick={() => {
                const h = parseHash()
                if (h) {
                  const maxV = verses.length > 0 ? verses[verses.length - 1] : 0
                  const minV = verses.length > 0 ? verses[0] : 0
                  setVerse(h.verse > minV ? h.verse - 1 : maxV)
                }
              }}>◀ Prev</button>

              <button className="secondary" style={{ flex: 1, padding: '8px 8px', fontSize: 14 }} onClick={() => {
                const h = parseHash()
                if (h) {
                  const maxV = verses.length > 0 ? verses[verses.length - 1] : 0
                  const minV = verses.length > 0 ? verses[0] : 0
                  setVerse(h.verse < maxV ? h.verse + 1 : minV)
                }
              }}>Next ▶</button>
            </div>

            <button className="secondary" style={{ width: '100%', fontSize: 14, padding: '8px 8px' }} onClick={copyCitation}>
              Copy Verse
            </button>
          </>
        )}
      </div>

      {/* Center — Verse + Commentary */}
      <div style={{ flexBasis: '50%', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {loading && <div className="empty"><span className="spinner"></span> Loading...</div>}

        {!loading && !result && (
          <div className="empty">Select a book, chapter, and verse to begin</div>
        )}

        {!loading && result && (
          <div className="card" style={{ margin: 0 }}>
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--accent)', marginBottom: 12 }}>
              {book} {chapter}
            </div>
            {result.verses.map(renderInterlinear)}
          </div>
        )}

        {!loading && result && (
          <div className="card" style={{ margin: 0 }}>
            <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--accent)', marginBottom: 8 }}>Commentary</div>
            {commentaryLoading && <div className="empty"><span className="spinner"></span> Loading...</div>}
            {!commentaryLoading && commentary.length === 0 && (
              <div className="empty">No commentary available</div>
            )}
            {!commentaryLoading && commentary.map((c, i) => {
              const label = c.source_name || c.source || 'Commentary'
              const text = c.commentary_text || c.chunk_text || ''
              return (
                <div key={i} style={{
                  marginBottom: 12, padding: 12,
                  background: 'var(--interlinear-bg)',
                  borderRadius: 6, border: '1px solid var(--interlinear-border)',
                }}>
                  <div style={{ fontSize: 14, color: 'var(--accent)', marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 16, lineHeight: 1.7, color: 'var(--text)', maxHeight: 300, overflow: 'hidden' }}>
                    {text}
                  </div>
                  {text.length > 1000 && (
                    <div style={{ marginTop: 4 }}>
                      <a href={BOOK_LINKS[book] || '#'} target="_blank" style={{ fontSize: 13, color: 'var(--text-muted)' }}
                        onClick={e => { e.preventDefault(); setToast({ msg: 'Open StudyLight.org in browser for full commentary', type: 'ok' }) }}>
                        Open full commentary →
                      </a>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Right sidebar — AI Chat (always visible) */}
      <div style={{
        flexBasis: '30%', minWidth: 240, flexShrink: 0,
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        display: 'flex', flexDirection: 'column',
        position: 'sticky', top: 68,
        maxHeight: 'calc(100vh - 84px)',
      }}>
        <div style={{
          padding: '12px 16px', borderBottom: '1px solid var(--border)',
          fontWeight: 600, fontSize: 16, color: 'var(--accent)',
        }}>
          AI Assistant
        </div>
        <div ref={chatRef} style={{
          flex: 1, overflowY: 'auto', padding: 16, fontSize: 15, lineHeight: 1.6,
        }}>
          {entries.length === 0 && !chatLoading && (
            <div className="empty" style={{ padding: 16, fontSize: 15 }}>
              Ask a question about this passage
            </div>
          )}
          {entries.map((e, i) => (
            <div key={i} style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600, marginBottom: 2 }}>Q: {e.question}</div>
              <div style={{ color: 'var(--text)', whiteSpace: 'pre-wrap' }}>{renderChatAnswer(e.answer)}</div>
            </div>
          ))}
          {chatLoading && <div className="empty" style={{ padding: 16 }}><span className="spinner"></span> Thinking...</div>}
        </div>
        <div style={{
          padding: 12, borderTop: '1px solid var(--border)',
          display: 'flex', gap: 8,
        }}>
          <input
            value={chatQuestion}
            onChange={e => setChatQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAsk()}
            placeholder="Ask about this passage..."
            style={{ flex: 1, fontSize: 15 }}
            disabled={chatLoading}
          />
          <button onClick={handleAsk} disabled={chatLoading || !chatQuestion.trim()} style={{ margin: 0, padding: '10px 18px' }}>
            Ask
          </button>
        </div>
      </div>
    </div>
  )
}

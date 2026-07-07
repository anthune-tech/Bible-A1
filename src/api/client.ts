import type {
  QueryResult, CommentaryEntry, CommentarySearchResult, CommentarySource,
  ChatResponse,
} from '../types'

const BASE = '/api'

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }))
    throw new Error(err.error || `HTTP ${r.status}`)
  }
  return r.json()
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }))
    throw new Error(err.error || `HTTP ${r.status}`)
  }
  return r.json()
}

export function getBooks(): Promise<string[]> {
  return get(`${BASE}/books`)
}

export function getChapters(book: string): Promise<number[]> {
  return get(`${BASE}/chapters?book=${encodeURIComponent(book)}`)
}

export function getVerses(book: string, chapter: number): Promise<number[]> {
  return get(`${BASE}/verses?book=${encodeURIComponent(book)}&chapter=${chapter}`)
}

export function queryVerse(
  book: string, chapter: number, verseStart: number, verseEnd: number, version = 'kjv',
): Promise<QueryResult> {
  return get(
    `${BASE}/query?book=${encodeURIComponent(book)}&chapter=${chapter}&verse=${verseStart}-${verseEnd}&version=${version}`,
  )
}

export function getCommentary(
  book: string, chapter: number, verse: number, studylight = false,
): Promise<CommentaryEntry[]> {
  return get(
    `${BASE}/commentary?book=${encodeURIComponent(book)}&chapter=${chapter}&verse=${verse}&studylight=${studylight}`,
  )
}

export function searchCommentary(q: string): Promise<CommentarySearchResult[]> {
  return get(`${BASE}/commentary/search?q=${encodeURIComponent(q)}`)
}

export function getCommentarySources(): Promise<CommentarySource[]> {
  return get(`${BASE}/commentary/sources`)
}

export function getModels(): Promise<string[]> {
  return get(`${BASE}/models`)
}

export function askAI(
  question: string, context = '', model = '', lang = 'en',
): Promise<ChatResponse> {
  return post(`${BASE}/ask`, { question, context, model, lang })
}




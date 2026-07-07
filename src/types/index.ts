export interface InterlinearWord {
  strong: string
  original: string
  transliteration: string
  gloss: string
  grammar?: string
}

export interface VerseData {
  verse: number
  reference: string
  text: string
  language: string
  interlinear: InterlinearWord[]
}

export interface QueryResult {
  book: string
  chapter: number
  verses: VerseData[]
}

export interface CommentaryEntry {
  id: number
  book_code: string
  chapter: number
  verse: number
  commentary_text?: string
  chunk_text?: string
  source: string
  source_name?: string
  source_type?: string
  verse_range?: string
  reference?: string
}

export interface CommentarySearchResult {
  rowid: number
  chunk_text: string
  source_abbr: string
  book_code: string
  chapter: number
  verse: number
  source_name: string
  reference: string
}

export interface CommentarySource {
  abbr: string
  name: string
  url: string | null
  chunk_count: number
}

export interface ChatResponse {
  answer: string
  tokens: number
}

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'

interface ChatEntry {
  question: string
  answer: string
}

interface ChatContextType {
  entries: ChatEntry[]
  addEntry: (question: string, answer: string) => void
  loading: boolean
  setLoading: (v: boolean) => void
  currentQuestion: string
  setCurrentQuestion: (v: string) => void
  clear: () => void
}

const ChatContext = createContext<ChatContextType | null>(null)
const STORAGE_KEY = 'bible-a1-chat'

function load(): ChatEntry[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function save(entries: ChatEntry[]) {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entries)) } catch { /* ignore */ }
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<ChatEntry[]>(load)
  const [loading, setLoading] = useState(false)
  const [currentQuestion, setCurrentQuestion] = useState('')

  useEffect(() => { save(entries) }, [entries])

  const addEntry = useCallback((question: string, answer: string) => {
    setEntries(prev => [...prev, { question, answer }])
  }, [])

  const clear = useCallback(() => setEntries([]), [])

  return (
    <ChatContext.Provider value={{ entries, addEntry, loading, setLoading, currentQuestion, setCurrentQuestion, clear }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat(): ChatContextType {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within ChatProvider')
  return ctx
}

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './ThemeContext'
import { ChatProvider } from './ChatContext'
import Layout from './components/Layout'
import BibleViewer from './pages/BibleViewer'
import Commentary from './pages/Commentary'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <ChatProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<BibleViewer />} />
            <Route path="/commentary" element={<Commentary />} />
          </Routes>
        </Layout>
        </ChatProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

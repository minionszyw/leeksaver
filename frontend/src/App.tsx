import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import ToastContainer from './components/ui/Toast'
import Home from './pages/Home'
import Watchlist from './pages/Watchlist'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-900 text-white">
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/watchlist" element={<Watchlist />} />
          </Routes>
        </Layout>
        <ToastContainer />
      </div>
    </BrowserRouter>
  )
}

export default App

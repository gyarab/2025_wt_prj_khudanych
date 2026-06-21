import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import HomePage from './pages/HomePage'

// App je "layout" — společný obal kolem všech stránek. Navbar nahoře a
// Footer dole zůstávají pořád stejné; mění se jen prostředek, který podle
// URL vybere <Routes>.
function App() {
  return (
    <>
      <Navbar />
      <main className="page-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
        </Routes>
      </main>
      <Footer />
    </>
  )
}

export default App

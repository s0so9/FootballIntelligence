import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'

function App() {
  return (
    <Router>
      <div className="app">
        <header className="app-header">
          <h1>Football Intelligence</h1>
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Home />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

function Home() {
  return (
    <div className="home">
      <h2>Football Intelligence Platform</h2>
      <p>Professional football analytics and prediction system</p>
      <p className="dev-notice">🚧 Under Development</p>
    </div>
  )
}

export default App

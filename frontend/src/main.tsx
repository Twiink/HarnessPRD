import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App.tsx'
import SessionList from './components/SessionList.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/projects" element={<SessionList />} />
        <Route path="/projects/:id" element={<App />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)

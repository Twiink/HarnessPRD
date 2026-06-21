import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App.tsx'
import AppV2 from './AppV2.tsx'
import SessionList from './components/SessionList.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/v2" element={<AppV2 />} />
        <Route path="/v2/list" element={<SessionList />} />
        <Route path="/v2/:id" element={<AppV2 />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import AppV2 from './AppV2.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {window.location.pathname === '/v2' ? <AppV2 /> : <App />}
  </React.StrictMode>,
)

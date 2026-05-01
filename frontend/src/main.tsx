import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { errorReporter } from './lib/errorReporter'

// Install global browser-error capture so unhandled errors / promise
// rejections show up alongside backend errors in the admin Logs bundle.
errorReporter.install()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

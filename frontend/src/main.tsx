import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { SpeedInsights } from '@vercel/speed-insights/react'
import App from './App'
import './styles.css'
import './compact.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode><App /><SpeedInsights /></StrictMode>,
)

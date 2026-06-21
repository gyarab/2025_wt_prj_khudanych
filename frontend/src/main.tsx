import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

// Initialize i18n before the app renders. This import runs the .init() in
// src/i18n/index.ts, registering the global instance the useTranslation hook
// reads from. Must come before <App/> renders so the first paint is localized.
import './i18n'

// Self-hosted Inter font (one .css per weight). These bundle the font files
// into our own build, so they load from our origin with no third-party
// round-trip to Google — which kills the FOUT "flicker". Weights here must
// match what global.css references (400/500/600/700).
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'

// Side-effect import: no variable, we just want the CSS injected globally.
// Vite sees this and bundles/injects the stylesheet. This is the ONE place
// global CSS gets loaded — everything below inherits the tokens.
import './styles/global.css'

// 1. Find the empty <div id="root"> from index.html.
// 2. Create a React "root" that owns that DOM node.
// 3. Render our <App /> tree into it.
//
// The `!` after getElementById tells TypeScript "trust me, this is not null".
// We know #root exists because index.html always ships it.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)

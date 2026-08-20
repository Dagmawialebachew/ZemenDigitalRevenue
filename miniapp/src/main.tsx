import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const rootElement = document.getElementById('root')

if (!rootElement) throw new Error('Missing #root element')

const root = createRoot(rootElement)

function StartupState({ message }: { message: string }) {
  return <div className="state-page"><div className="z-loader"><i/><i/><i/></div><p>{message}</p></div>
}

function loadTelegramBridge(timeoutMs = 3000) {
  if (window.Telegram?.WebApp) return Promise.resolve()

  return new Promise<void>((resolve) => {
    const script = document.createElement('script')
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timeout)
      resolve()
    }
    const timeout = window.setTimeout(finish, timeoutMs)

    script.src = 'https://telegram.org/js/telegram-web-app.js?63'
    script.async = true
    script.onload = finish
    script.onerror = finish
    document.head.appendChild(script)
  })
}

async function start() {
  root.render(<StartupState message="Opening Zemen…" />)
  await loadTelegramBridge()
  const { default: App } = await import('./App')
  root.render(<StrictMode><App /></StrictMode>)
}

void start().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : 'The app could not start.'
  root.render(<div className="state-page"><div className="state-mark">!</div><h2>Startup failed</h2><p>{message}</p></div>)
})

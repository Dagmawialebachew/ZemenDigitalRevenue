import { useEffect, useState } from 'react'

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true
}

export function InstallControl() {
  const [prompt, setPrompt] = useState<InstallPromptEvent | null>(null)

  useEffect(() => {
    const capture = (event: Event) => {
      event.preventDefault()
      setPrompt(event as InstallPromptEvent)
    }
    const installed = () => setPrompt(null)
    window.addEventListener('beforeinstallprompt', capture)
    window.addEventListener('appinstalled', installed)
    return () => {
      window.removeEventListener('beforeinstallprompt', capture)
      window.removeEventListener('appinstalled', installed)
    }
  }, [])

  if (!prompt || isStandalone()) return null

  const install = async () => {
    await prompt.prompt()
    await prompt.userChoice
    setPrompt(null)
  }

  return <button className="install-control" onClick={() => void install()} title="Install Zemen Control on this computer">
    <span>↓</span> Install app
  </button>
}

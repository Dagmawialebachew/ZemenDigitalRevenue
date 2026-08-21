interface TgButton {
  text: string
  color: string
  textColor: string
  isVisible: boolean
  setParams(params: Record<string, unknown>): TgButton
  onClick(callback: () => void): TgButton
  offClick(callback: () => void): TgButton
  show(): TgButton
  hide(): TgButton
  enable(): TgButton
  disable(): TgButton
  showProgress(leaveActive?: boolean): TgButton
  hideProgress(): TgButton
}

interface TelegramWebApp {
  initData: string
  version: string
  platform: string
  colorScheme: string
  ready(): void
  expand(): void
  close(): void
  setHeaderColor(color: string): void
  setBackgroundColor(color: string): void
  setBottomBarColor(color: string): void
  enableClosingConfirmation(): void
  disableVerticalSwipes?(): void
  enableVerticalSwipes?(): void
  openTelegramLink(url: string): void
  openLink(url: string): void
  showPopup(params: { title?: string; message: string; buttons?: Array<{ id?: string; type?: string; text?: string }> }, callback?: (id: string) => void): void
  HapticFeedback?: {
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
    notificationOccurred(type: 'error' | 'success' | 'warning'): void
    selectionChanged(): void
  }
  BackButton: {
    isVisible: boolean
    show(): void
    hide(): void
    onClick(callback: () => void): void
    offClick(callback: () => void): void
  }
  MainButton: TgButton
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp }
  }
}

export const tg = window.Telegram?.WebApp

export function prepareTelegramShell() {
  if (!tg) return
  tg.ready()
  tg.expand()
  tg.setHeaderColor('#050605')
  tg.setBackgroundColor('#050605')
  tg.setBottomBarColor('#07110b')
  tg.disableVerticalSwipes?.()
}

export function haptic(type: 'tap' | 'success' | 'warning' = 'tap') {
  if (!tg?.HapticFeedback) return
  if (type === 'success') tg.HapticFeedback.notificationOccurred('success')
  else if (type === 'warning') tg.HapticFeedback.notificationOccurred('warning')
  else tg.HapticFeedback.impactOccurred('light')
}

export function openTelegram(url: string) {
  if (!url) return
  if (tg) tg.openTelegramLink(url)
  else window.location.href = url
}

export function openExternal(url: string) {
  if (!url) return
  if (tg) {
    tg.openLink(url)
    return
  }
  const opened = window.open(url, '_blank', 'noopener,noreferrer')
  if (!opened) window.location.href = url
}

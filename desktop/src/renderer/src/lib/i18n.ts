// The app's text in the user's language. The source text is Chinese (the app's first language) and is its own key, as
// with gettext: English comes from locales/en.json, and anything missing there stays Chinese.
//
//   tr('已完成 {done}/{total} 个阶段。', { done, total })  a message, placeholders filled in
//   tr('{n} 帧', { n })                                     an English plural: the entry is ["{n} frame", "{n} frames"]
//   mark('线性处理')                                        a message translated later, where it is shown (tr(value))
//
// The language comes from the backend (Settings: follow the system, 中文, English) and is remembered here so the next
// start shows the right one at once. tests/test_i18n.py checks that every Chinese string goes through tr() or mark()
// and has its English entry.
import { create } from 'zustand'
import en from '@/locales/en.json'

export type Language = 'zh' | 'en'
type Values = Record<string, string | number>

const CATALOGS: Record<Language, Record<string, string | string[]> | null> = { zh: null, en }
const STORAGE_KEY = 'astroflow-language'

function initial(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'zh' || saved === 'en') return saved
  } catch {
    // storage unavailable: guess from the browser
  }
  return navigator.language?.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

export const useLanguage = create<{ language: Language }>(() => ({ language: initial() }))

export function setLanguage(language: Language): void {
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // not remembered: the backend tells us again next time
  }
  if (useLanguage.getState().language !== language) useLanguage.setState({ language })
}

/** `text` in the current language with {placeholders} filled in from `values`. */
export function tr(text: string, values?: Values): string {
  const entry = CATALOGS[useLanguage.getState().language]?.[text]
  let out = text
  if (Array.isArray(entry)) out = entry[values?.n === 1 ? 0 : 1]
  else if (entry) out = entry
  return values ? out.replace(/\{(\w+)\}/g, (m, key: string) => (key in values ? String(values[key]) : m)) : out
}

/** A message translated where it is shown (tr(value)); marks it for the catalog check. */
export const mark = (text: string): string => text

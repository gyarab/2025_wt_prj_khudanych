/**
 * i18n setup (react-i18next + i18next).
 *
 * Importing this module once (from main.tsx) initializes a single global
 * i18next instance. Components then read translations via the `useTranslation`
 * hook — they never import this file directly.
 *
 * We start with English only, but the structure is built so adding a locale
 * later is two lines: import the JSON and add it to `resources`.
 */
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'

// The locales we support. `as const` makes this a readonly tuple of literal
// strings ('en'), which we derive the SupportedLocale type from below.
export const SUPPORTED_LOCALES = ['en'] as const
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number] // 'en'

void i18n
  // Plug react-i18next into i18next so the useTranslation hook works and
  // components re-render when the language changes.
  .use(initReactI18next)
  .init({
    // Every locale lives under a "namespace"; 'translation' is the default.
    resources: {
      en: { translation: en },
    },
    lng: 'en', // active language
    fallbackLng: 'en', // used when a key is missing in the active language
    interpolation: {
      // React already escapes values before inserting them into the DOM,
      // so i18next doesn't need to escape again (would double-escape).
      escapeValue: false,
    },
  })

export default i18n

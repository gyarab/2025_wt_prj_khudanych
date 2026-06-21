/**
 * TypeScript augmentation for i18next.
 *
 * By telling i18next's types what our resources look like (the shape of
 * en.json), the `t()` function becomes fully typed: editors autocomplete
 * valid keys, and passing a key that doesn't exist is a compile error.
 *
 * This file has no runtime output — it only refines existing types
 * (declaration merging via `declare module`).
 */
import 'i18next'
import en from './locales/en.json'

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: {
      translation: typeof en
    }
  }
}

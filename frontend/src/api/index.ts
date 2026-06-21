/**
 * Barrel file: re-exports the public surface of the api/ folder so callers can
 * write a single tidy import:
 *
 *   import { getCountries, type Country } from '@/api'
 *
 * instead of reaching into individual files. One front door for the whole layer.
 */
export type { Country } from './types'
export { ApiError } from './client'
export { getCountries } from './countries'

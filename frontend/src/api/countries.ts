/**
 * Country-related API calls. Each endpoint the backend exposes gets one
 * small, named function here, so components never hardcode URLs — they call
 * `getCountries()` and get back a typed `Country[]`.
 */
import { apiGet } from './client'
import type { Country } from './types'

/**
 * GET /api/countries
 *
 * Returns every country, already sorted by score (descending) on the server.
 * For now we fetch the whole list and shape it in the browser; when the
 * dataset grows we'll add server-side pagination/search and change only this
 * function's internals — callers won't notice.
 */
export function getCountries(signal?: AbortSignal): Promise<Country[]> {
  return apiGet<Country[]>('/api/countries', signal)
}

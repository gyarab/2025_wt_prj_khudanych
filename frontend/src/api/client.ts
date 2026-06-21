/**
 * A tiny typed wrapper around the browser's built-in fetch().
 *
 * Why wrap fetch at all? Three reasons:
 *   1. One place to set headers, handle errors, and (later) a base URL.
 *   2. fetch() does NOT throw on HTTP errors (404/500) — it only rejects on
 *      network failure. We add the "throw on bad status" behaviour everyone
 *      actually wants.
 *   3. Generics let each caller declare the response shape, so the rest of
 *      the app gets fully-typed data instead of `any`.
 */

/** Thrown when the server responds with a non-2xx status. */
export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * GET a JSON resource and return it typed as `T`.
 *
 * @param path   e.g. "/api/countries" — relative, so Vite's dev proxy (and
 *               the prod reverse proxy) forward it to Django.
 * @param signal optional AbortSignal to cancel the request (used to clean up
 *               when a React component unmounts mid-flight).
 *
 * The <T> is a type parameter: the caller decides what shape comes back, e.g.
 * `apiGet<Country[]>('/api/countries')`. Note this is a COMPILE-TIME promise
 * only — see the honest caveat in the lesson notes.
 */
export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw new ApiError(
      `GET ${path} failed with status ${response.status}`,
      response.status,
    )
  }

  // res.json() is typed as Promise<any>; we assert it matches T. This is the
  // trust boundary between "untyped network data" and "typed app code".
  return response.json() as Promise<T>
}

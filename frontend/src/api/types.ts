/**
 * TypeScript shapes for the data the API returns.
 *
 * This `Country` interface mirrors the backend's `CountryOut` Pydantic schema
 * (prj/app/api.py) field-for-field. It is the single source of truth for what
 * a country looks like on the frontend — every component that touches country
 * data imports this type, so if the backend shape changes, we update it here
 * once and TypeScript flags every place that needs attention.
 */
export interface Country {
  cca3: string            // ISO 3166-1 alpha-3, e.g. "CZE" (primary key)
  cca2: string            // ISO 3166-1 alpha-2, e.g. "CZ"
  name_common: string     // "Czechia"
  name_official: string   // "Czech Republic"
  capital: string         // may be "" (blank), never null
  region: string          // "Europe"
  subregion: string       // "Central Europe", may be ""
  population: number       // BigInteger on the backend → just a number here
  area_km2: number | null // Optional[float] on the backend → can be null
  flag_svg: string        // URL to the SVG flag
  flag_png: string        // URL to the PNG flag
  is_independent: boolean
  upvotes: number
  downvotes: number
  score: number           // computed server-side: upvotes - downvotes
}

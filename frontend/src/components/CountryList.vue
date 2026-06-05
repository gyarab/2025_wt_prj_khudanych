<script setup>
import { ref, onMounted, computed } from 'vue'

// --- State ---
// ref() creates reactive variables. When .value changes, Vue re-renders whatever uses it.
const countries = ref([])    // the full list returned by the API
const loading = ref(true)    // true while the fetch is in-flight
const error = ref(null)      // holds the error message string if something fails
const searchQuery = ref('')  // bound to the search input via v-model

// --- Data fetching ---
const loadCountries = () => {
  loading.value = true
  error.value = null

  // fetch() returns a Promise — non-blocking network call
  fetch('/api/countries')
    .then(response => {
      if (!response.ok) throw new Error(`Chyba serveru: ${response.status}`)
      return response.json()   // parse the JSON body → another Promise
    })
    .then(data => {
      countries.value = data   // store the array; Vue auto-rerenders the grid
      loading.value = false
    })
    .catch(err => {
      error.value = err.message
      loading.value = false
    })
}

// --- Derived state ---
// computed() caches its result and only recalculates when countries or searchQuery changes.
// The filter runs entirely in the browser — no extra API call on every keystroke.
const filteredCountries = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return countries.value
  return countries.value.filter(c =>
    c.name_common.toLowerCase().includes(q) ||
    c.cca3.toLowerCase().includes(q)
  )
})

// --- Lifecycle ---
// onMounted fires once, right after Vue inserts this component into the page.
onMounted(() => {
  loadCountries()
})
</script>

<template>
  <div class="page-wrapper">

    <!-- Page header -->
    <div class="page-header">
      <h1 class="page-title">Country Database</h1>
      <p class="page-subtitle">Browse and explore world nations, territories and dependencies.</p>
    </div>

    <!-- Search & counter bar -->
    <div class="control-bar">
      <div class="search-box">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.5"/>
          <path d="M11 11L14 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <input
          v-model="searchQuery"
          type="search"
          id="country-search"
          placeholder="Search by name or code (CZE)…"
          autocomplete="off"
          spellcheck="false"
        />
        <!-- Clear button appears only when there is text -->
        <button
          v-if="searchQuery"
          class="clear-btn"
          @click="searchQuery = ''"
          aria-label="Clear search"
        >×</button>
      </div>

      <div v-if="!loading && !error" class="counter-pill">
        {{ filteredCountries.length }}
        <span>{{ filteredCountries.length === 1 ? 'country' : 'countries' }}</span>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="feedback-state">
      <div class="spinner" role="status" aria-label="Loading"></div>
      <p>Loading countries…</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="feedback-state feedback-state--error">
      <p class="error-msg">⚠️ {{ error }}</p>
      <button class="retry-btn" @click="loadCountries">Try again</button>
    </div>

    <!-- Empty search result -->
    <div v-else-if="filteredCountries.length === 0" class="feedback-state">
      <p>No countries match "<strong>{{ searchQuery }}</strong>"</p>
      <button class="retry-btn" @click="searchQuery = ''">Clear search</button>
    </div>

    <!-- Country grid -->
    <div v-else class="countries-grid">
      <!--
        v-for loops over filteredCountries and renders one card per item.
        :key gives Vue a stable identity so it only updates changed cards.
      -->
      <article
        v-for="country in filteredCountries"
        :key="country.cca3"
        class="country-card"
      >
        <!-- Flag image with a fixed aspect ratio to prevent layout shift -->
        <div class="flag-wrapper">
          <img
            :src="country.flag_svg"
            :alt="`Flag of ${country.name_common}`"
            loading="lazy"
          />
          <!-- ISO code badge overlaid on the flag -->
          <span class="cca3-badge">{{ country.cca3 }}</span>
        </div>

        <div class="card-body">
          <!-- :title shows the full official name on hover when it's truncated -->
          <h3 class="country-name" :title="country.name_official">
            {{ country.name_common }}
          </h3>
          <p class="country-region">{{ country.region }}</p>

          <div class="card-footer">
            <span class="score-label">Score</span>
            <!--
              Dynamic class: adds .positive or .negative based on the score value.
              The ternary adds a "+" prefix only for positive numbers.
            -->
            <span
              class="score-badge"
              :class="country.score >= 0 ? 'score-badge--positive' : 'score-badge--negative'"
            >
              {{ country.score > 0 ? '+' : '' }}{{ country.score }}
            </span>
          </div>
        </div>
      </article>
    </div>

  </div>
</template>

<style scoped>
/* ── Page wrapper ─────────────────────────────────────────── */
.page-wrapper {
  /* no extra padding needed; .page-content in App.vue handles it */
}

/* ── Page header ──────────────────────────────────────────── */
.page-header {
  margin-bottom: 2rem;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-heading);
  letter-spacing: -0.03em;
  margin-bottom: 0.3rem;
}

.page-subtitle {
  font-size: 0.9rem;
  color: var(--text-muted);
}

/* ── Control bar (search + counter) ──────────────────────── */
.control-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
  flex-wrap: wrap;
}

/* Search box */
.search-box {
  position: relative;
  flex: 1;
  min-width: 0;          /* allow shrinking below 260px on small phones */
  max-width: 440px;
}

@media (max-width: 640px) {
  .search-box {
    /* stretch the full width on mobile so the counter pill wraps below */
    max-width: 100%;
    width: 100%;
  }
}

.search-icon {
  position: absolute;
  left: 0.875rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;        /* clicks pass through to the input */
}

.search-box input {
  width: 100%;
  padding: 0.625rem 2.5rem 0.625rem 2.5rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  color: var(--text);
  outline: none;
  transition: border-color var(--duration) var(--ease),
              box-shadow    var(--duration) var(--ease);
  /* Remove the native browser ×  so we can use our own */
  -webkit-appearance: none;
}

.search-box input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

/* Custom clear button */
.clear-btn {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: var(--text-muted);
  line-height: 1;
  padding: 0 0.125rem;
  transition: color var(--duration) var(--ease);
}
.clear-btn:hover { color: var(--text-heading); }

/* Counter pill */
.counter-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.75rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 9999px;         /* pill shape */
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-heading);
  white-space: nowrap;
}
.counter-pill span { font-weight: 400; color: var(--text-muted); }

/* ── Feedback states (loading / error / empty) ────────────── */
.feedback-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 5rem 1rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.feedback-state strong { color: var(--text-heading); }

.feedback-state--error { color: var(--error); }

/* Spinner */
.spinner {
  width: 36px;
  height: 36px;
  border: 2.5px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Retry / clear button */
.retry-btn {
  padding: 0.45rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--font-sans);
  font-size: 0.85rem;
  color: var(--text);
  cursor: pointer;
  transition: border-color var(--duration) var(--ease),
              box-shadow    var(--duration) var(--ease);
}
.retry-btn:hover {
  border-color: var(--border-focus);
  box-shadow: var(--shadow-xs);
}

/* ── Country grid ─────────────────────────────────────────── */
.countries-grid {
  display: grid;
  /*
    auto-fill: create as many columns as fit.
    minmax(240px, 1fr): each column is at least 240px, then stretches equally.
  */
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1.25rem;
}

/* ── Country card ─────────────────────────────────────────── */
.country-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
  transition: transform   var(--duration) var(--ease),
              box-shadow  var(--duration) var(--ease),
              border-color var(--duration) var(--ease);
  cursor: default;
}

.country-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
  border-color: #d0cec8;
}

/* Flag */
.flag-wrapper {
  position: relative;
  /*
    aspect-ratio locks the proportions so the image container never jumps
    as images load — prevents Cumulative Layout Shift (CLS).
  */
  aspect-ratio: 16 / 10;
  /*
    object-fit: contain (set on the img below) can leave empty strips on the
    sides of flags with unusual ratios (Nepal is square, Switzerland is square…).
    A subtle dot pattern fills that space without looking like a plain blank.
  */
  background-color: var(--surface-alt);
  background-image: radial-gradient(circle, var(--border) 1px, transparent 1px);
  background-size: 12px 12px;
  overflow: hidden;
}

.flag-wrapper img {
  width: 100%;
  height: 100%;
  /*
    contain = scale the image to fit entirely inside the box.
    No cropping — the whole flag is always visible.
    (cover = fill the box and crop whatever doesn't fit — that was the bug.)
  */
  object-fit: contain;
  display: block;
}

.cca3-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  color: var(--text-heading);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 3px 7px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(0,0,0,0.06);
  line-height: 1.4;
}

/* Card body */
.card-body {
  padding: 1rem 1.1rem 1.1rem;
  display: flex;
  flex-direction: column;
  flex: 1;              /* stretch so all cards in a row are the same height */
}

.country-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-heading);
  margin-bottom: 0.2rem;
  /* Truncate long names to a single line with an ellipsis */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.country-region {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 0.9rem;
}

/* Card footer — score row */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;          /* pushes footer to the bottom of the card */
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}

.score-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.score-badge {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.score-badge--positive {
  color: var(--success);
  background: var(--success-bg);
}

.score-badge--negative {
  color: var(--error);
  background: var(--error-bg);
}
</style>
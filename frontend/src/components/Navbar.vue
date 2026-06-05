<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

// ref() tracks whether the mobile menu is open or closed.
// When it flips, Vue re-renders only the parts of the template that depend on it.
const menuOpen = ref(false)

const toggle = () => { menuOpen.value = !menuOpen.value }

// Close the menu whenever the user navigates (taps a link).
const close = () => { menuOpen.value = false }
</script>

<template>
  <header class="navbar">
    <div class="navbar-inner">

      <!-- Logo -->
      <RouterLink to="/" class="logo" @click="close">
        <span class="logo-icon">🌐</span>
        <span class="logo-text">JEF <strong>DB</strong></span>
      </RouterLink>

      <!-- Desktop nav — hidden on mobile via CSS -->
      <nav class="links" aria-label="Main navigation">
        <RouterLink to="/" class="nav-link" @click="close">Státy</RouterLink>
        <a href="/api/docs" target="_blank" class="nav-link nav-link--external">
          API Docs
          <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M2 10L10 2M10 2H5M10 2V7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </a>
      </nav>

      <!--
        Hamburger button — only visible on mobile.
        aria-expanded tells screen readers whether the menu is open.
        aria-controls links it to the mobile-menu element below.
      -->
      <button
        class="hamburger"
        :class="{ 'is-open': menuOpen }"
        @click="toggle"
        :aria-expanded="menuOpen"
        aria-controls="mobile-menu"
        aria-label="Toggle navigation menu"
      >
        <!--
          Three spans = three bars of the hamburger.
          CSS transitions animate them into an × when .is-open is applied.
        -->
        <span class="bar"></span>
        <span class="bar"></span>
        <span class="bar"></span>
      </button>
    </div>

    <!--
      Mobile drawer — slides in from the top when menuOpen is true.
      v-show keeps the element in the DOM (unlike v-if) so the CSS
      transition always plays both on open AND close.
    -->
    <div
      id="mobile-menu"
      class="mobile-menu"
      :class="{ 'is-open': menuOpen }"
      aria-hidden="!menuOpen"
    >
      <nav class="mobile-links" aria-label="Mobile navigation">
        <RouterLink to="/" class="mobile-link" @click="close">Státy</RouterLink>
        <a href="/api/docs" target="_blank" class="mobile-link" @click="close">
          API Docs
          <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M2 10L10 2M10 2H5M10 2V7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </a>
      </nav>
    </div>
  </header>
</template>

<style scoped>
/* ── Base navbar shell ───────────────────────────────────── */
.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  /* Semi-transparent so the frosted-glass blur effect shows content beneath */
  background: rgba(247, 246, 243, 0.9);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border);
}

/* ── Inner row (logo + nav/hamburger) ───────────────────── */
.navbar-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 1.5rem;
  height: 60px;
}

/* ── Logo ───────────────────────────────────────────────── */
.logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: var(--text-heading);
  font-size: 1rem;
  font-weight: 500;
  letter-spacing: -0.01em;
  transition: opacity var(--duration) var(--ease);
}
.logo:hover { opacity: 0.7; color: var(--text-heading); }
.logo-icon  { font-size: 1.1rem; }
.logo-text strong { font-weight: 700; }

/* ── Desktop nav links ──────────────────────────────────── */
.links {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-muted);
  text-decoration: none;
  transition: color var(--duration) var(--ease),
              background var(--duration) var(--ease);
}
.nav-link:hover,
.nav-link.router-link-active {
  color: var(--text-heading);
  background: var(--surface-alt);
}
.nav-link--external svg { opacity: 0.5; flex-shrink: 0; }

/* ── Hamburger button ───────────────────────────────────── */
/*
  Hidden on desktop — only shown when the viewport is narrow.
  We use display:none / display:flex toggled via a media query.
*/
.hamburger {
  display: none;           /* hidden by default (desktop) */
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 5px;
  width: 36px;
  height: 36px;
  padding: 0;
  background: none;
  border: none;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background var(--duration) var(--ease);
}
.hamburger:hover { background: var(--surface-alt); }

/* The three bars */
.bar {
  display: block;
  width: 20px;
  height: 1.5px;
  background: var(--text-heading);
  border-radius: 2px;
  /*
    We animate three separate properties:
    - transform-origin: rotation pivots from the center of each bar
    - transform: rotates top/bottom bars into a cross, moves middle out
    - opacity: fades the middle bar out
  */
  transform-origin: center;
  transition: transform 0.25s var(--ease),
              opacity   0.25s var(--ease);
}

/* ×  animation — applied when .is-open is on the button */
.hamburger.is-open .bar:nth-child(1) {
  transform: translateY(6.5px) rotate(45deg);
}
.hamburger.is-open .bar:nth-child(2) {
  opacity: 0;
  transform: scaleX(0);
}
.hamburger.is-open .bar:nth-child(3) {
  transform: translateY(-6.5px) rotate(-45deg);
}

/* ── Mobile drawer ──────────────────────────────────────── */
/*
  Slides in from above using max-height + overflow hidden.
  This is the most reliable CSS-only way to animate height:auto
  (you can't animate from 0 to 'auto' directly in CSS).
*/
.mobile-menu {
  max-height: 0;
  overflow: hidden;
  /*
    ease-in for close (fast start → slow end = snappy collapse)
    We use a single transition here; open uses a different easing below.
  */
  transition: max-height 0.28s ease-in;
  border-top: 0px solid var(--border); /* starts invisible */
}

.mobile-menu.is-open {
  max-height: 300px;   /* tall enough for any number of links */
  border-top-width: 1px;
  transition: max-height 0.3s ease-out; /* ease-out = slower start, smooth reveal */
}

/* Links inside the drawer */
.mobile-links {
  display: flex;
  flex-direction: column;
  padding: 0.5rem 1.5rem 1rem;
  gap: 0.25rem;
  max-width: 1280px;
  margin: 0 auto;
}

.mobile-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text-muted);
  text-decoration: none;
  transition: color var(--duration) var(--ease),
              background var(--duration) var(--ease);
}
.mobile-link:hover,
.mobile-link.router-link-active {
  color: var(--text-heading);
  background: var(--surface-alt);
}
.mobile-link svg { opacity: 0.5; }

/* ── Responsive breakpoint ──────────────────────────────── */
/*
  Below 640px: hide the desktop nav, show the hamburger.
  640px is a common "small tablet / large phone" breakpoint.
*/
@media (max-width: 640px) {
  .links     { display: none; }
  .hamburger { display: flex; }
}
</style>
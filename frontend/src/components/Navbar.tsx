import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { cx } from '@/utils/cx'
import logoUrl from '@/assets/logo.svg'
import styles from './Navbar.module.css'

function Navbar() {
  const { t } = useTranslation()

  // Vue mělo: const menuOpen = ref(false)
  // React má: pár [hodnota, setter]. menuOpen čteš, setMenuOpen mění.
  const [menuOpen, setMenuOpen] = useState(false)

  // Vue: const toggle = () => { menuOpen.value = !menuOpen.value }
  // React: setter umí dostat funkci (open) => nováHodnota. open je aktuální stav.
  const toggle = () => setMenuOpen((open) => !open)
  const close = () => setMenuOpen(false)

  return (
    <header className={styles.navbar}>
      <div className={styles.navbarInner}>
        {/* Logo — Link nepřenačítá stránku (na rozdíl od <a>) */}
        <Link to="/" className={styles.logo} onClick={close}>
          <img src={logoUrl} className={styles.logoImg} alt="" />
          <span className={styles.logoText}>
            JEF <strong>DB</strong>
          </span>
        </Link>

        {/* Desktop navigace — na mobilu ji schová CSS */}
        <nav className={styles.links} aria-label="Main navigation">
          {/* NavLink sám pozná, jestli míří na aktuální URL → isActive.
              className tu není string, ale FUNKCE, které router předá { isActive }. */}
          <NavLink
            to="/"
            end
            onClick={close}
            className={({ isActive }) => cx(styles.navLink, isActive && styles.active)}
          >
            {t('nav.home')}
          </NavLink>

          {/* Externí odkaz necháváme jako <a> — opouští SPA, jde mimo router. */}
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className={cx(styles.navLink, styles.navLinkExternal)}
          >
            {t('nav.apiDocs')}
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path
                d="M2 10L10 2M10 2H5M10 2V7"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </a>
        </nav>

        {/* Hamburger — jen na mobilu. aria-* pomáhá čtečkám pro nevidomé. */}
        <button
          type="button"
          className={cx(styles.hamburger, menuOpen && styles.isOpen)}
          onClick={toggle}
          aria-expanded={menuOpen}
          aria-controls="mobile-menu"
          aria-label={t('nav.toggle')}
        >
          <span className={styles.bar} />
          <span className={styles.bar} />
          <span className={styles.bar} />
        </button>
      </div>

      {/* Mobilní zásuvka — vždy v DOM, otevírání řeší CSS přes .isOpen
          (animace max-height). To je jako Vue v-show, ne v-if. */}
      <div id="mobile-menu" className={cx(styles.mobileMenu, menuOpen && styles.isOpen)}>
        <nav className={styles.mobileLinks} aria-label="Mobile navigation">
          <NavLink
            to="/"
            end
            onClick={close}
            className={({ isActive }) => cx(styles.mobileLink, isActive && styles.active)}
          >
            {t('nav.home')}
          </NavLink>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className={styles.mobileLink}
            onClick={close}
          >
            {t('nav.apiDocs')}
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path
                d="M2 10L10 2M10 2H5M10 2V7"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </a>
        </nav>
      </div>
    </header>
  )
}

export default Navbar

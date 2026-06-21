import { useTranslation } from 'react-i18next'
import styles from './Footer.module.css'

function Footer() {
  const { t } = useTranslation()

  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        <span>{t('brand.copyright')}</span>
        <span className={styles.separator} aria-hidden="true">·</span>
        <a
          className={styles.footerLink}
          href="/api/docs"
          target="_blank"
          rel="noopener noreferrer"
        >
          {t('nav.apiDocs')}
        </a>
      </div>
    </footer>
  )
}

export default Footer

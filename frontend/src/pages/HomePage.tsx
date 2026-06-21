import { useTranslation } from 'react-i18next'

// Zatím jen placeholder (zástupná stránka). V Lekci 6 z toho postavíme
// celou domovskou stránku (hero, statistiky, žebříčky, regiony).
function HomePage() {
  const { t } = useTranslation()

  return (
    <div>
      <h1>{t('home.heroTitle')}</h1>
      <p>{t('home.heroSubtitle')}</p>
    </div>
  )
}

export default HomePage

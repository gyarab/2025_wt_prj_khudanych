import {createRouter, createWebHistory} from 'vue-router'
import CountryList from '../components/CountryList.vue'

const router = createRouter({
  // BASE_URL = '/' lokálně, '/app/' v produkci (viz vite.config.js / VITE_BASE).
  // Díky tomu funguje client-side routování i když SPA běží pod /app/.
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
        path: '/',
        name: 'Home',
        component: CountryList
    }
  ]
})

export default router
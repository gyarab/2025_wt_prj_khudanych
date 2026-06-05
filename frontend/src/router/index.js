import {createRouter, createWebHistory} from 'vue-router'
import CountryList from '../components/CountryList.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
        path: '/',
        name: 'Home',
        component: CountryList
    }
  ]
})

export default router
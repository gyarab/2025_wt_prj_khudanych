<script setup>
import { ref, onMounted } from 'vue'

const countries = ref([])
const loading = ref(true)
const error = ref(null)

const loadCountries = () => {
  fetch('/api/countries')
    .then(response => {
      if (!response.ok) throw new Error(`Chyba serveru: ${response.status}`)
      return response.json()
    })
    .then(data => {
      countries.value = data
      loading.value = false
    })
    .catch(err => {
      error.value = err.message
      loading.value = false
    })
}

onMounted(() => {
  loadCountries()
})
</script>

<template>
  <div>
    <div v-if="loading" class="status">Načítám data z Django API...</div>
    <div v-else-if="error" class="status error">Chyba: {{ error }}</div>

    <div v-else class="grid">
      <div v-for="country in countries" :key="country.cca3" class="card">
        <img :src="country.flag_svg" :alt="country.name_common" loading="lazy" />
        <h3>{{ country.name_common }}</h3>
        <p class="code">{{ country.cca3 }}</p>
        <p class="score">Skóre: {{ country.score }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 'scoped' zajišťuje, že se styly nepromítnou mimo tuto komponentu */
.status { text-align: center; font-size: 1.2rem; margin-top: 50px; }
.error { color: #ff6b6b; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 25px; margin-top: 30px; }
.card { background-color: #1e1e1e; border: 1px solid #2d2d2d; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
.card img { width: 100%; height: 120px; object-fit: cover; border-radius: 4px; }
.card h3 { margin: 15px 0 5px 0; font-size: 1.1rem; color: #fff; }
.code { color: #888; font-size: 0.9rem; margin: 0 0 10px 0; }
.score { font-weight: bold; color: #007acc; margin: 0; }
</style>
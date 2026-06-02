<script setup>
import CountryList from './components/CountryList.vue'
</script>

<template>
  <main class="container">
    <h1>Just Enough Flags</h1>
    <CountryList />
  </main>
</template>

<style>
:root {
  font-family: system-ui, -apple-system, sans-serif;
  background-color: #121212;
  color: #e0e0e0;
}
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 20px;
}
h1 {
  text-align: center;
  color: #fff;
}
</style>
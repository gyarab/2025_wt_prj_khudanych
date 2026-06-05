<script setup>
import { RouterView } from 'vue-router'
import Navbar from './components/Navbar.vue'
import Footer from './components/Footer.vue'
</script>

<template>
  <div id="app">
    <Navbar />
    <main class="page-content">
      <RouterView />
    </main>
    <Footer />
  </div>
</template>

<style>
/* page-content sits between the sticky navbar and the footer */
.page-content {
  flex: 1;
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
}

@media (max-width: 640px) {
  .page-content {
    padding: 1.5rem 1rem 3rem;
  }
}
</style>
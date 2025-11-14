<template>
  <div id="app">
    <AppHeader v-if="!hideHeader" />
    <main class="main-content">
      <router-view />
    </main>
    <AppFooter v-if="!hideFooter" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'

const route = useRoute()
const hideHeader = computed(() => !!route.meta?.hideHeader)
const hideFooter = computed(() => !!route.meta?.hideFooter)
</script>

<style>
#app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  width: 100%;
  font-family: 'Arial', sans-serif;
}

.main-content {
  flex: 1;
  background-color: #f5f7fa;
  padding: 1rem 0;
  width: 100%;
  padding-bottom: 0px;
}

.app-footer {
  width: 100%;
  text-align: center;
  color: #888;
  font-size: 14px;
  padding: 16px 0;
  background: #f5f5f5;
}
</style>
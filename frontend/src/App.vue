<template>
  <div id="app">
    <AppHeader />
    <main class="main-content">
      <router-view />
    </main>
    <AppFooter />
  </div>
</template>

<script setup>
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue' // 简单页脚组件
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
}
</style>
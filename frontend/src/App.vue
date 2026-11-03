<template>
  <RouterView />
  <AppToast />
</template>

<script setup>
import { RouterView } from 'vue-router'
import AppToast from '@/components/ui/AppToast.vue'
</script>

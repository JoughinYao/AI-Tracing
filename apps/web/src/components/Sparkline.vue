<template>
  <div class="sparkline">
    <span
      v-for="(point, index) in points"
      :key="index"
      class="spark-bar"
      :style="{ height: `${Math.max(12, point * 100)}%` }"
    />
  </div>
</template>

<script setup lang="ts">
defineProps<{ points: number[] }>();
</script>

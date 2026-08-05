<template>
  <div class="characters-mobile">
    <LorebookEditor :visible="true" :embedded="true" mode="characters" />
  </div>
</template>

<script setup lang="ts">
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
</script>

<style scoped>
.characters-mobile {
  width: 100%;
  min-height: 72vh;
  height: 100%;
  overflow: hidden;
  background: var(--spark-bg);
}
</style>

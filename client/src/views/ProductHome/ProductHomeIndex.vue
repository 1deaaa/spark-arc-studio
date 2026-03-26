
<script setup lang="ts">
import { useMobile } from '../../composables/useMobile';
import Desktop from './ProductHomeDesktop.vue';
import Mobile from './ProductHomeMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>


<script setup lang="ts">
import { useMobile } from '../../composables/useMobile';
import Desktop from './WorldDesktop.vue';
import Mobile from './WorldMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>


<script setup>
import { useMobile } from '../../composables/useMobile';
import Desktop from './SynopsisDesktop.vue';
import Mobile from './SynopsisMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

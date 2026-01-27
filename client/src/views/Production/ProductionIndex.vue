
<script setup>
import { useMobile } from '../../composables/useMobile';
import Desktop from './ProductionDesktop.vue';
import Mobile from './ProductionMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

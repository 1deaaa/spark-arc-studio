
<script setup>
import { useMobile } from '../../composables/useMobile';
import Desktop from './LorebookDesktop.vue';
import Mobile from './LorebookMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

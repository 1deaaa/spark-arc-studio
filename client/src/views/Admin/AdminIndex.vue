
<script setup>
import { useMobile } from '../../composables/useMobile';
import Desktop from './AdminDesktop.vue';
import Mobile from './AdminMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

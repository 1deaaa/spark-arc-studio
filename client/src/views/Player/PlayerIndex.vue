
<script setup>
import { useMobile } from '../../composables/useMobile';
import Desktop from './PlayerDesktop.vue';
import Mobile from './PlayerMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

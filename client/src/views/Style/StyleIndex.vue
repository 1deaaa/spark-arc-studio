
<script setup lang="ts">
import { useMobile } from '../../composables/useMobile';
import Desktop from './StyleDesktop.vue';
import Mobile from './StyleMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

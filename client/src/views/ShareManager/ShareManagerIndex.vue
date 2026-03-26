
<script setup lang="ts">
import { useMobile } from '../../composables/useMobile';
import Desktop from './ShareManagerDesktop.vue';
import Mobile from './ShareManagerMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

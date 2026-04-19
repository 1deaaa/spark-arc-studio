
<script setup lang="ts">
import { useMobile } from '../../composables/useMobile';
import Desktop from './DashboardDesktop.vue';
import Mobile from './DashboardMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>


<script setup>
import { useMobile } from '../../composables/useMobile';
import Desktop from './EngineDesktop.vue';
import Mobile from './EngineMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

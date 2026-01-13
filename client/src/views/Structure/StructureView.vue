
<script setup>
import { useMobile } from '../../composables/useMobile';
import Desktop from './StructureDesktop.vue';
import Mobile from './StructureMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

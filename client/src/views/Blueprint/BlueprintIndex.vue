
<script setup>
import { useMobile } from '../../composables/useMobile';
import Desktop from './BlueprintDesktop.vue';
import Mobile from './BlueprintMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

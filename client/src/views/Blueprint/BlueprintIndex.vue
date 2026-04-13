
<script setup lang="ts">
import { useMobile } from '../../composables/useMobile';
import Desktop from './BlueprintDesktop.vue';
import MobileNew from './BlueprintMobileNew.vue';

const { isMobile } = useMobile();
</script>

<template>
  <MobileNew v-if="isMobile" />
  <Desktop v-else />
</template>

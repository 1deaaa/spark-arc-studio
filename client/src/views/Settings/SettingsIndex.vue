
<script setup lang="ts">
import { useMobile } from '../../composables/useMobile';
import Desktop from './SettingsDesktop.vue';
import Mobile from './SettingsMobile.vue';

const { isMobile } = useMobile();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

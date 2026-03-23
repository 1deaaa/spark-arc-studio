
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useMobile } from '../../composables/useMobile';
import Desktop from './PlayerDesktop.vue';
import Mobile from './PlayerMobile.vue';
import NovelPlayerReader from './NovelPlayerReader.vue';
import { resolveApiUrl } from '@/services/apiClient';

const { isMobile } = useMobile();
const route = useRoute();
const loadingFormat = ref(true);
const playFormat = ref('script');

const activePlayer = computed(() => {
  if (loadingFormat.value) return null;
  if (playFormat.value === 'novel') return NovelPlayerReader;
  return isMobile.value ? Mobile : Desktop;
});

async function detectFormat() {
  loadingFormat.value = true;
  try {
    const shareId = String(route.params.shareId || '');
    const isVersionPlay = route.path.includes('/play/v/');
    const infoUrl = isVersionPlay ? `/api/play/v/${shareId}/info` : `/api/play/${shareId}/info`;
    const response = await fetch(resolveApiUrl(infoUrl));
    if (!response.ok) {
      playFormat.value = 'script';
      return;
    }
    const info = await response.json();
    playFormat.value = info.content_format === 'novel' ? 'novel' : 'script';
  } catch {
    playFormat.value = 'script';
  } finally {
    loadingFormat.value = false;
  }
}

onMounted(() => {
  detectFormat();
});
</script>

<template>
  <component :is="activePlayer" v-if="activePlayer" />
</template>

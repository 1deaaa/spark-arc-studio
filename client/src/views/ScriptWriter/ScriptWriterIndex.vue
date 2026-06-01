
<script setup lang="ts">
import { useMobile } from '../../composables/useMobile';
import Desktop from './ScriptWriterDesktop.vue';
import Mobile from '../../components/layouts/mobile/MobileWorkspace.vue';
import { useScriptWriterLogic } from '../../composables/useScriptWriterLogic';

const { isMobile } = useMobile();
const { initialSync } = useScriptWriterLogic();

// 全局路由与状态同步初始化
initialSync();
</script>

<template>
  <Mobile v-if="isMobile" />
  <Desktop v-else />
</template>

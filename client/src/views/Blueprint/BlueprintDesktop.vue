<template>
  <StoryBlueprint :projectId="projectId" />
</template>

<script setup>
import StoryBlueprint from '../../components/dlg-editor/StoryBlueprint.vue';

defineProps({
  projectId: {
    type: [String, Number],
    default: null
  }
});
</script>

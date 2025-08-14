<template>
  <div class="project-selector fancy">
    <label for="project-dropdown" class="selector-label">项目</label>
    <div class="project-select-wrapper">
      <select
        id="project-dropdown"
        class="styled-select"
        :value="projectStore.currentProject"
        @change="projectStore.setCurrentProject($event.target.value)"
      >
        <option v-for="project in projectStore.projects" :key="project" :value="project">
          {{ project }}
        </option>
      </select>
      <div class="project-actions">
        <button @click="projectStore.createProject" class="btn-icon" title="新建项目">➕</button>
        <button @click="projectStore.deleteCurrentProject" class="btn-icon danger" title="删除当前项目">🗑️</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useProjectStore } from '@/stores/projectStore';

const projectStore = useProjectStore();

onMounted(() => {
  projectStore.loadProjects();
});
</script>
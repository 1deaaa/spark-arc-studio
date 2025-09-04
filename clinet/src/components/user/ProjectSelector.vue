<template>
  <div class="project-selector fancy">
    <label for="project-dropdown" class="selector-label">项目</label>
    <div class="project-select-wrapper">
      <select
        id="project-dropdown"
        class="styled-select"
        :value="projectStore.currentProject"
        @change="onProjectChange($event.target.value)"
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
import { useRouter } from 'vue-router';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';

const projectStore = useProjectStore();
const fileStore = useFileStore();
const router = useRouter();

async function onProjectChange(projectId) {
  await projectStore.setCurrentProject(projectId);
  await fileStore.loadFiles(projectId);
  if (fileStore.files.length > 0) {
    const firstFile = fileStore.files;
    if (firstFile) {
      const fileName = firstFile.name;
      const fileId = fileName.substring(0, fileName.lastIndexOf('.'));
      
      if (fileName.endsWith('.story')) {
        router.push(`/projects/${projectId}/files/${fileId}`);
      } else if (fileName.endsWith('.lorebook')) {
        router.push(`/projects/${projectId}/lorebooks/${fileId}`);
      }
    }
  }
}

onMounted(() => {
  projectStore.loadProjects();
});
</script>
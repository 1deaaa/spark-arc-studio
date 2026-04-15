<template>
  <n-space align="center" :size="12">
    <n-text style="font-size: var(--spark-fs-xs); opacity: 0.8">{{ t('components.projectSelector.project') }}</n-text>
    <n-select
      :value="projectStore.currentProject"
      @update:value="onProjectChange"
      :options="projectOptions"
      style="min-width: 180px"
      :consistent-menu-width="false"
    >
      <!-- @vue-ignore -->
      <template #prefix>
        <n-icon :component="FolderOpenOutline" />
      </template>
    </n-select>
    <n-space :size="6">
      <n-button 
        circle 
        @click="projectStore.createProject" 
        :title="t('components.projectSelector.newProject')"
        size="small"
      >
        <template #icon>
          <n-icon :component="AddCircleOutline" />
        </template>
      </n-button>
      <n-popconfirm 
        @positive-click="projectStore.deleteCurrentProject"
        :positive-text="t('common.delete')"
        :negative-text="t('common.cancel')"
        type="warning"
      >
        <template #trigger>
          <n-button 
            circle 
            type="error"
            :title="t('components.projectSelector.deleteCurrentProject')"
            size="small"
          >
            <template #icon>
              <n-icon :component="TrashOutline" />
            </template>
          </n-button>
        </template>
        <template #default>
          {{ t('components.projectSelector.confirmDelete', { project: projectStore.currentProject }) }}
          <br/>
          <n-text type="error" style="font-weight: 600;">
            {{ t('components.projectSelector.confirmDeleteWarning') }}
          </n-text>
        </template>
      </n-popconfirm>
    </n-space>
  </n-space>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { NSpace, NText, NSelect, NButton, NIcon, NPopconfirm } from 'naive-ui';
import { FolderOpenOutline, AddCircleOutline, TrashOutline } from '@vicons/ionicons5';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';

const { t } = useI18n();

const projectStore = useProjectStore();
const fileStore = useFileStore();
const router = useRouter();

const projectOptions = computed(() => 
  projectStore.projects.map(p => ({
    label: p,
    value: p
  }))
);

async function onProjectChange(projectId) {
  await projectStore.setCurrentProject(projectId);
  await fileStore.loadFileTree(projectId);
}

onMounted(() => {
  projectStore.loadProjects();
});
</script>

<style scoped>
/* 移除旧样式，使用 Naive UI 默认样式 */
</style>
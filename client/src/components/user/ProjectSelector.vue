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
        <n-icon :component="FolderOpen" />
      </template>
    </n-select>
    <n-space :size="6">
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button
            circle
            @click="projectStore.createProject"
            size="small"
          >
            <template #icon>
              <n-icon :component="CirclePlus" />
            </template>
          </n-button>
        </template>
        {{ t('components.projectSelector.newProject') }}
      </n-tooltip>
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button
            circle
            @click="handleRenameProject"
            size="small"
          >
            <template #icon>
              <n-icon :component="SquarePen" />
            </template>
          </n-button>
        </template>
        {{ t('components.projectSelector.renameCurrentProject') }}
      </n-tooltip>
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button
            circle
            type="error"
            @click="handleDeleteProject"
            size="small"
          >
            <template #icon>
              <n-icon :component="Trash" />
            </template>
          </n-button>
        </template>
        {{ t('components.projectSelector.deleteCurrentProject') }}
      </n-tooltip>
    </n-space>
  </n-space>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { NSpace, NText, NSelect, NButton, NIcon, NTooltip, useDialog } from 'naive-ui';
import { CirclePlus, FolderOpen, SquarePen, Trash } from 'lucide-vue-next';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';
import bus from '@/eventBus';

const { t } = useI18n();
const dialog = useDialog();

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

async function handleRenameProject() {
  if (!projectStore.currentProject) return;
  const newName = await new Promise<unknown>((resolve) => bus.emit('prompt', {
    title: t('components.projectSelector.renameProject'),
    message: t('components.projectSelector.renamePrompt', { project: projectStore.currentProject }),
    defaultValue: projectStore.currentProject,
    resolve,
  }));
  if (typeof newName === 'string' && newName.trim()) {
    await projectStore.renameCurrentProject(newName);
  }
}

function handleDeleteProject() {
  if (!projectStore.currentProject) return;
  // 第一次确认
  dialog.warning({
    title: t('components.projectSelector.confirmDeleteTitle'),
    content: t('components.projectSelector.confirmDelete', { project: projectStore.currentProject }),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: () => {
      // 第二次确认
      dialog.error({
        title: t('components.projectSelector.confirmDeleteTitle'),
        content: t('components.projectSelector.confirmDeleteFinal', { project: projectStore.currentProject }),
        positiveText: t('common.delete'),
        negativeText: t('common.cancel'),
        onPositiveClick: () => {
          projectStore.deleteCurrentProject();
        },
      });
    },
  });
}

onMounted(() => {
  projectStore.loadProjects();
});
</script>

<style scoped>
/* 移除旧样式，使用 Naive UI 默认样式 */
</style>

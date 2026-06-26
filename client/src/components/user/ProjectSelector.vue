<template>
  <n-space align="center" :size="12">
    <n-text style="font-size: var(--spark-fs-xs); opacity: 0.8">{{ t('components.projectSelector.project') }}</n-text>
    <n-select
      :value="projectStore.currentProject"
      @update:value="onProjectChange"
      :options="projectOptions"
      :render-label="renderProjectLabel"
      style="min-width: 180px"
      :consistent-menu-width="false"
    >
      <!-- @vue-ignore -->
      <template #prefix>
        <n-icon
          :component="currentProjectModeIcon"
          class="project-select-mode-icon"
          :class="`is-${currentProjectMode}`"
        />
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
      <StoryTagsPanel />
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
import { onMounted, computed, h } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { NSpace, NText, NSelect, NButton, NIcon, NTooltip, useDialog, type SelectOption } from 'naive-ui';
import { BookOpen, CirclePlus, Clapperboard, SquarePen, Trash } from '@lucide/vue';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';
import bus from '@/eventBus';
import StoryTagsPanel from '../share/StoryTagsPanel.vue';

type ProjectWorkspaceMode = 'script' | 'novel';

const { t } = useI18n();
const dialog = useDialog();

const projectStore = useProjectStore();
const fileStore = useFileStore();
const router = useRouter();

const projectOptions = computed(() =>
  projectStore.projects.map(p => ({
    label: p,
    value: p,
    mode: projectStore.projectMode(p),
  }))
);

const currentProjectMode = computed<ProjectWorkspaceMode>(() => projectStore.projectMode(projectStore.currentProject));
const currentProjectModeIcon = computed(() => getProjectModeIcon(currentProjectMode.value));

function getProjectModeIcon(mode: string | undefined) {
  return mode === 'novel' ? BookOpen : Clapperboard;
}

function renderProjectLabel(option: SelectOption) {
  const mode = option.mode === 'novel' ? 'novel' : 'script';
  const icon = getProjectModeIcon(mode);
  return h('div', {
    class: 'project-option-label',
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '8px',
      minWidth: '0',
      lineHeight: '1.2',
    },
  }, [
    h(NIcon, {
      class: ['project-option-mode-icon', `is-${mode}`],
      size: 16,
      style: {
        color: 'var(--spark-primary)',
        flex: '0 0 auto',
        transform: 'translateY(1.5px)',
      },
    }, { default: () => h(icon) }),
    h('span', {
      class: 'project-option-name',
      style: {
        minWidth: '0',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      },
    }, String(option.label ?? '')),
  ]);
}

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
.project-select-mode-icon {
  color: var(--spark-primary);
  transform: translateY(1.5px);
}

.project-select-mode-icon.is-novel {
  color: var(--spark-primary);
}

.project-option-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.project-option-mode-icon {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
}

.project-option-mode-icon.is-script {
  color: var(--spark-primary);
  background: color-mix(in srgb, var(--spark-primary), transparent 86%);
}

.project-option-mode-icon.is-novel {
  color: var(--spark-primary);
  background: color-mix(in srgb, var(--spark-primary), transparent 86%);
}

.project-option-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

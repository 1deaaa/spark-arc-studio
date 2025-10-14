<template>
  <n-space align="center" :size="12">
    <n-text style="font-size: 12px; opacity: 0.8">项目</n-text>
    <n-select
      :value="projectStore.currentProject"
      @update:value="onProjectChange"
      :options="projectOptions"
      style="min-width: 180px"
      :consistent-menu-width="false"
    >
      <template #prefix>
        <n-icon :component="FolderOpenOutline" />
      </template>
    </n-select>
    <n-space :size="6">
      <n-button 
        circle 
        @click="projectStore.createProject" 
        title="新建项目"
        size="small"
      >
        <template #icon>
          <n-icon :component="AddCircleOutline" />
        </template>
      </n-button>
      <n-popconfirm 
        @positive-click="projectStore.deleteCurrentProject"
        positive-text="删除"
        negative-text="取消"
      >
        <template #trigger>
          <n-button 
            circle 
            type="error"
            title="删除当前项目"
            size="small"
          >
            <template #icon>
              <n-icon :component="TrashOutline" />
            </template>
          </n-button>
        </template>
        确定要删除项目 "{{ projectStore.currentProject }}" 吗？
      </n-popconfirm>
    </n-space>
  </n-space>
</template>

<script setup>
import { onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { NSpace, NText, NSelect, NButton, NIcon, NPopconfirm } from 'naive-ui';
import { FolderOpenOutline, AddCircleOutline, TrashOutline } from '@vicons/ionicons5';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';

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
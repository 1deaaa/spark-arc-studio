<template>
  <div class="version-manager">
    <div class="header">
      <div class="left">
        <div class="title-row">
          <h3>发布管理</h3>
          <n-tag size="small" :type="contentFormat === 'novel' ? 'warning' : 'info'">
            当前工作模式：{{ contentFormat === 'novel' ? '小说' : '剧本' }}
          </n-tag>
        </div>
        <n-text depth="3" class="subtitle">管理项目的发布版本、历史备份和分享链接</n-text>
      </div>
      <n-space align="center">
        <n-button type="primary" @click="openCreateModal">
          <template #icon><n-icon :component="SaveOutline" /></template>
          发布新版本
        </n-button>
      </n-space>
    </div>

    <div class="filter-bar" v-if="!projectId">
      <n-select 
        v-model:value="filterProject" 
        :options="projectOptions" 
        placeholder="筛选项目" 
        clearable 
        @update:value="loadVersions"
        style="width: 200px"
      />
    </div>

    <n-spin :show="loading">
      <div class="version-list">
        <n-empty v-if="versions.length === 0" description="暂无版本记录" />
        
        <n-card v-for="ver in versions" :key="ver.id" class="version-item" size="small">
          <template #header>
            <div class="version-header">
              <span class="version-title">{{ ver.version_name }}</span>
              <n-tag size="small" :type="ver.content_format === 'novel' ? 'warning' : 'info'">
                {{ ver.content_format === 'novel' ? '小说' : '剧本' }}
              </n-tag>
            </div>
          </template>
          <template #header-extra>
            <n-text depth="3" size="small">{{ formatDate(ver.created_at) }}</n-text>
          </template>
          
          <div class="version-content">
            <div class="version-desc">{{ ver.description || '无描述' }}</div>
            <n-space class="version-top-actions" justify="end" align="center" wrap>
              <n-button size="small" secondary @click="downloadVersionSnapshot(ver)">
                <template #icon><n-icon :component="CloudDownloadOutline" /></template>
                {{ ver.content_format === 'novel' ? '导出小说' : '导出脚本' }}
              </n-button>

              <n-popconfirm v-if="ver.content_format !== 'novel'" @positive-click="restoreVersion(ver)">
                <template #trigger>
                  <n-button size="small" secondary>
                    <template #icon><n-icon :component="RefreshOutline" /></template>
                    恢复到此版本
                  </n-button>
                </template>
                确定要将当前剧本回滚到此版本吗？当前未保存的修改可能会丢失。
              </n-popconfirm>

              <n-popconfirm @positive-click="deleteVersion(ver.id)">
                <template #trigger>
                  <n-button size="small" type="error" ghost>
                    <template #icon><n-icon :component="TrashOutline" /></template>
                  </n-button>
                </template>
                确定要删除这个版本吗？
              </n-popconfirm>
            </n-space>
          </div>
          
          <template #action>
            <div class="action-row">
              <div class="action-right-group">
                <n-space class="action-buttons" align="center" wrap>
                  <n-button size="small" :disabled="!ver.is_shared" @click="copyLink(ver.share_id)">
                    <template #icon><n-icon :component="CopyOutline" /></template>
                    复制链接
                  </n-button>

                  <n-button size="small" @click="editVersion(ver)">
                    <template #icon><n-icon :component="CreateOutline" /></template>
                    编辑
                  </n-button>
                  
                  <n-button size="small" type="info" @click="openLink(ver.share_id || ver.id)">
                    <template #icon><n-icon :component="PlayOutline" /></template>
                    {{ ver.content_format === 'novel' ? '试看' : '试玩' }}
                  </n-button>
                </n-space>

                <div class="share-toggle" :title="ver.is_shared ? '公开分享中，点击切换为私有' : '当前为私有，点击切换为公开'">
                  <n-text depth="3" class="share-state-label">{{ ver.is_shared ? '公开' : '私有' }}</n-text>
                  <n-switch
                    size="small"
                    :value="ver.is_shared"
                    @update:value="toggleShare(ver, $event)"
                  />
                </div>
              </div>
            </div>
          </template>
        </n-card>
      </div>
    </n-spin>

    <!-- Create/Edit Modal -->
    <n-modal v-model:show="showModal" preset="card" :title="isEditing ? '编辑版本信息' : '创建新版本'" style="width: 500px">
      <n-form label-placement="top">
        <n-form-item label="所属项目" v-if="!projectId && !isEditing">
          <n-select v-model:value="formModel.projectName" :options="projectOptions" />
        </n-form-item>
        <n-form-item label="版本名称">
          <n-input v-model:value="formModel.versionName" placeholder="例如: v1.0, 测试版, 第一次修改..." />
        </n-form-item>
        <n-form-item v-if="!isEditing" label="版本类型">
          <n-select v-model:value="formModel.contentFormat" :options="formatOptions" />
        </n-form-item>
        <n-form-item label="描述 (可选)">
          <n-input v-model:value="formModel.description" type="textarea" placeholder="备注信息..." />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="submitting" @click="submitForm" :disabled="!canSubmit">
            {{ isEditing ? '保存' : '创建' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { 
  NButton, NIcon, NCard, NEmpty, NTag, NSpace, NPopconfirm, NModal, 
  NForm, NFormItem, NSelect, NInput, NSwitch, NSpin, 
  NText, useMessage 
} from 'naive-ui';
import { 
  CopyOutline, PlayOutline, TrashOutline, SaveOutline, 
  CreateOutline, RefreshOutline, CloudDownloadOutline,
} from '@vicons/ionicons5';
import { fetchWithAuth } from '@/services/api';
import { exportProjectToSQLite } from '@/services/projectService';
import { useProjectStore } from '@/components/stores/projectStore';

type ContentFormat = 'script' | 'novel';

type VersionListItem = {
  id: number;
  project_name: string;
  version_name: string;
  description?: string;
  created_at?: string | null;
  content_format?: ContentFormat | null;
  is_shared?: boolean;
  share_id?: string | number | null;
  share_url?: string | null;
  share_url_public?: string | null;
};

type VersionFormModel = {
  id: number | null;
  projectName: string | null;
  versionName: string;
  description: string;
  contentFormat: ContentFormat;
};

type SaveFilePickerWritable = {
  write: (data: Blob) => Promise<void>;
  close: () => Promise<void>;
};

type SaveFilePickerHandle = {
  createWritable: () => Promise<SaveFilePickerWritable>;
};

type SaveFilePickerOptions = {
  suggestedName?: string;
  types?: Array<{
    description: string;
    accept: Record<string, string[]>;
  }>;
};

type WindowWithSaveFilePicker = Window & {
  showSaveFilePicker?: (options?: SaveFilePickerOptions) => Promise<SaveFilePickerHandle>;
};

const props = defineProps({
  projectId: { type: String, default: null },
  contentFormat: { type: String, default: 'script' }
});

const message = useMessage();
const projectStore = useProjectStore();

const versions = ref<VersionListItem[]>([]);
const loading = ref(false);
const showModal = ref(false);
const submitting = ref(false);
const exporting = ref(false);
const isEditing = ref(false);
const filterProject = ref<string | null>(null);

const formModel = ref<VersionFormModel>({
  id: null,
  projectName: null,
  versionName: '',
  description: '',
  contentFormat: props.contentFormat === 'novel' ? 'novel' : 'script'
});

const contentFormat = computed(() => props.contentFormat === 'novel' ? 'novel' : 'script');

const formatOptions = [
  { label: '剧本', value: 'script' },
  { label: '小说', value: 'novel' },
];

const projectOptions = computed(() => {
  return projectStore.projects.map(p => ({ label: p, value: p }));
});

const canSubmit = computed(() => {
  if (isEditing.value) return !!formModel.value.versionName;
  return (props.projectId || formModel.value.projectName) && formModel.value.versionName;
});

async function loadVersions() {
  const targetProject = props.projectId || filterProject.value;
  if (!targetProject) {
    versions.value = [];
    return;
  }

  loading.value = true;
  try {
    const res = await fetchWithAuth(`/api/versions/${targetProject}`);
    if (res.ok) {
      versions.value = await res.json();
    }
  } catch (e) {
    message.error('加载版本列表失败');
  } finally {
    loading.value = false;
  }
}

async function exportDatabase(specificProject: string | null = null) {
  const targetProject = specificProject || props.projectId || filterProject.value;
  if (!targetProject) {
    message.warning('请先选择一个项目');
    return;
  }

  exporting.value = true;
  try {
    // 使用新的下载端点获取数据库文件
    const response = await fetchWithAuth('/api/export-to-sqlite/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: targetProject, reset: true }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.message || '导出失败');
    }

    const blob = await response.blob();
    const chapters = response.headers.get('X-Chapters') || '0';
    const scenes = response.headers.get('X-Scenes') || '0';
    const defaultFilename = `${targetProject}_stories.db`;

    // 尝试使用现代 File System Access API（Chrome/Edge 支持）
    const typedWindow = window as WindowWithSaveFilePicker;
    if (typeof typedWindow.showSaveFilePicker === 'function') {
      try {
        const handle = await typedWindow.showSaveFilePicker({
          suggestedName: defaultFilename,
          types: [{
            description: 'SQLite 数据库',
            accept: { 'application/x-sqlite3': ['.db'] },
          }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        message.success(`导出完成：章节 ${chapters}，场景 ${scenes}`);
        return;
      } catch (err: unknown) {
        // 用户取消选择时不报错
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        // 其他错误回退到传统下载
        console.warn('showSaveFilePicker 失败，回退到传统下载:', err);
      }
    }

    // 回退方案：传统 <a> 下载
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = defaultFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success(`导出完成：章节 ${chapters}，场景 ${scenes}`);
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error('导出失败: ' + errorMessage);
  } finally {
    exporting.value = false;
  }
}

function openCreateModal() {
  isEditing.value = false;
  formModel.value = {
    id: null,
    projectName: props.projectId || filterProject.value || null,
    versionName: generateDefaultTitle(),
    description: '',
    contentFormat: contentFormat.value
  };
  showModal.value = true;
}

function generateDefaultTitle() {
  const date = new Date();
  const pad = (n) => n.toString().padStart(2, '0');
  return `v${date.getFullYear()}${pad(date.getMonth()+1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}`;
}

function editVersion(ver: VersionListItem) {
  isEditing.value = true;
  formModel.value = {
    id: ver.id,
    projectName: ver.project_name,
    versionName: ver.version_name,
    description: ver.description || '',
    contentFormat: ver.content_format || 'script'
  };
  showModal.value = true;
}

async function submitForm() {
  submitting.value = true;
  try {
    const targetProject = props.projectId || formModel.value.projectName;
    if (isEditing.value) {
      // Update
      const res = await fetchWithAuth(`/api/versions/${formModel.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          versionName: formModel.value.versionName,
          description: formModel.value.description
        })
      });
      if (res.ok) {
        message.success('更新成功');
        showModal.value = false;
        loadVersions();
      } else {
        message.error('更新失败');
      }
    } else {
      // Create
        const res = await fetchWithAuth(`/api/versions/${targetProject}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          versionName: formModel.value.versionName,
          description: formModel.value.description,
          contentFormat: formModel.value.contentFormat || contentFormat.value
        })
      });
      if (res.ok) {
        message.success('版本快照已创建');
        showModal.value = false;
        loadVersions();
      } else {
        const err = await res.json();
        message.error(err.error || '创建失败');
      }
    }
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error('操作失败: ' + errorMessage);
  } finally {
    submitting.value = false;
  }
}

async function toggleShare(ver, value) {
  const oldVal = ver.is_shared;
  ver.is_shared = value;
  try {
    const res = await fetchWithAuth(`/api/versions/${ver.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_shared: value })
    });
    if (!res.ok) throw new Error();

    const data = await res.json().catch(() => ({}));
    if (value && data.share_id) {
      ver.share_id = data.share_id;
    }
    
    message.success(value ? '已设为公开' : '已设为私有');
  } catch (e) {
    ver.is_shared = oldVal;
    message.error('状态更新失败');
  }
}

async function deleteVersion(id) {
  try {
    const res = await fetchWithAuth(`/api/versions/${id}`, { method: 'DELETE' });
    if (res.ok) {
      message.success('删除成功');
      loadVersions();
    } else {
      message.error('删除失败');
    }
  } catch (e) {
    message.error('删除失败');
  }
}

async function restoreVersion(ver) {
  try {
    const res = await fetchWithAuth(`/api/versions/${ver.id}/restore`, { method: 'POST' });
    if (res.ok) {
      message.success('版本已恢复，请刷新页面查看最新内容');
      // 触发全局事件或刷新
      window.location.reload(); 
    } else {
      const err = await res.json();
      message.error(err.error || '恢复失败');
    }
  } catch (e) {
    message.error('恢复操作失败');
  }
}

async function downloadVersionSnapshot(ver) {
  try {
    const response = await fetchWithAuth(`/api/versions/${ver.id}/download`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || '下载失败');
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const nameMatch = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
    const filename = decodeURIComponent(nameMatch?.[1] || nameMatch?.[2] || `${ver.version_name}.${ver.content_format === 'novel' ? 'md' : 'db'}`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success(ver.content_format === 'novel' ? '小说快照已导出' : '剧本快照已导出');
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error('导出失败: ' + errorMessage);
  }
}

function copyLink(shareId) {
  if (!shareId) return;
  // 使用当前页面的基础路径（包含子路径和端口），确保链接在任何部署环境下都有效
  const baseUrl = window.location.href.split('#')[0];
  const url = `${baseUrl}#/play/v/${shareId}`;
  navigator.clipboard.writeText(url).then(() => {
    message.success('分享链接已复制');
  });
}

function openLink(shareId) {
  if (!shareId) return;
  // 使用相对路径（不带开头的 /），确保在子路径部署时不会跳到根域名
  const url = `#/play/v/${shareId}`;
  window.open(url, '_blank');
}

function formatDate(isoStr) {
  return new Date(isoStr).toLocaleString();
}

watch(() => props.projectId, () => {
  loadVersions();
});

onMounted(() => {
  loadVersions();
  if (projectStore.projects.length === 0) {
    projectStore.loadProjects();
  }
});
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.subtitle {
  font-size: 0.9em;
}

.filter-bar {
  margin-bottom: 16px;
}

.version-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-content {
  margin: 8px 0;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
}

.version-desc {
  color: var(--n-text-color-3);
  font-size: 0.9em;
  flex: 1 1 auto;
  min-width: 0;
}

.version-top-actions {
  flex: 0 0 auto;
  align-self: center;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.action-right-group {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}

.action-buttons {
  flex: 0 0 auto;
  min-width: 0;
  justify-content: flex-end;
}

.share-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
  flex: 0 0 auto;
}

.share-state-label {
  min-width: 2.5em;
  text-align: right;
  color: var(--n-primary-color);
  font-weight: 600;
}

.version-title {
  font-weight: bold;
}

.version-desc {
  color: var(--n-text-color-3);
  font-size: 0.9em;
}

@media (max-width: 720px) {
  .version-content,
  .action-row {
    flex-direction: column;
    align-items: stretch;
  }

  .version-top-actions,
  .action-buttons,
  .share-toggle {
    width: 100%;
    justify-content: flex-start;
    min-width: 0;
    margin-left: 0;
  }

  .action-right-group {
    width: 100%;
    margin-left: 0;
    flex-direction: column;
    align-items: stretch;
  }

  .title-row {
    align-items: flex-start;
  }
}
</style>

<template>
  <div class="version-manager">
    <div class="header">
      <div class="left">
        <h3>发布管理</h3>
        <n-text depth="3" class="subtitle">管理项目的发布版本、历史备份和分享链接</n-text>
      </div>
      <n-button type="primary" @click="openCreateModal">
        <template #icon><n-icon :component="SaveOutline" /></template>
        发布新版本
      </n-button>
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
              <n-tag v-if="ver.is_shared" type="success" size="small" round>已分享</n-tag>
              <n-tag v-else type="default" size="small" round>私有</n-tag>
            </div>
          </template>
          <template #header-extra>
            <n-text depth="3" size="small">{{ formatDate(ver.created_at) }}</n-text>
          </template>
          
          <div class="version-content">
            <div class="version-desc">{{ ver.description || '无描述' }}</div>
          </div>
          
          <template #action>
            <n-space justify="end" align="center">
              <n-switch :value="ver.is_shared" @update:value="(v) => toggleShare(ver, v)" size="small">
                <template #checked>公开分享</template>
                <template #unchecked>私有</template>
              </n-switch>
              
              <n-divider vertical />

              <n-button size="small" @click="editVersion(ver)">
                <template #icon><n-icon :component="CreateOutline" /></template>
                编辑
              </n-button>

              <n-button size="small" v-if="ver.is_shared" @click="copyLink(ver.share_id)">
                <template #icon><n-icon :component="CopyOutline" /></template>
                链接
              </n-button>
              
              <n-button size="small" v-if="ver.is_shared" type="info" @click="openLink(ver.share_id)">
                <template #icon><n-icon :component="PlayOutline" /></template>
                试玩
              </n-button>

              <n-popconfirm @positive-click="restoreVersion(ver)">
                <template #trigger>
                  <n-button size="small" type="warning" ghost>
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

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { 
  NButton, NIcon, NCard, NEmpty, NTag, NSpace, NPopconfirm, NModal, 
  NForm, NFormItem, NSelect, NInput, NSwitch, NDivider, NSpin, 
  NText, useMessage 
} from 'naive-ui';
import { 
  CopyOutline, PlayOutline, TrashOutline, SaveOutline, 
  CreateOutline, RefreshOutline 
} from '@vicons/ionicons5';
import { fetchWithAuth } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';

const props = defineProps({
  projectId: { type: String, default: null }
});

const message = useMessage();
const projectStore = useProjectStore();

const versions = ref([]);
const loading = ref(false);
const showModal = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const filterProject = ref(null);

const formModel = ref({
  id: null,
  projectName: null,
  versionName: '',
  description: ''
});

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

function openCreateModal() {
  isEditing.value = false;
  formModel.value = {
    id: null,
    projectName: props.projectId || filterProject.value || null,
    versionName: generateDefaultTitle(),
    description: ''
  };
  showModal.value = true;
}

function generateDefaultTitle() {
  const date = new Date();
  const pad = (n) => n.toString().padStart(2, '0');
  return `v${date.getFullYear()}${pad(date.getMonth()+1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}`;
}

function editVersion(ver) {
  isEditing.value = true;
  formModel.value = {
    id: ver.id,
    projectName: ver.project_name,
    versionName: ver.version_name,
    description: ver.description
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
          description: formModel.value.description
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
  } catch (e) {
    message.error('操作失败: ' + e.message);
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
    
    // 重新加载以获取 share_id
    if (value) await loadVersions();
    
    message.success(value ? '已开启公开分享' : '已关闭分享');
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

function copyLink(shareId) {
  if (!shareId) return;
  const url = `${window.location.origin}/#/play/v/${shareId}`;
  navigator.clipboard.writeText(url).then(() => {
    message.success('分享链接已复制');
  });
}

function openLink(shareId) {
  if (!shareId) return;
  const url = `/#/play/v/${shareId}`;
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

.version-title {
  font-weight: bold;
}

.version-content {
  margin: 8px 0;
}

.version-desc {
  color: var(--n-text-color-3);
  font-size: 0.9em;
}
</style>

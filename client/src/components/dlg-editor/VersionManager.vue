<template>
  <div class="version-manager">
    <div class="header">
      <div class="left">
        <h3>版本与备份</h3>
        <n-text depth="3" class="subtitle">管理项目的历史版本和分享链接</n-text>
      </div>
      <n-button type="primary" @click="openCreateModal">
        <template #icon><n-icon :component="SaveOutline" /></template>
        创建新版本
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
              <span class="version-title">{{ ver.title }}</span>
              <n-tag v-if="ver.is_shared" type="success" size="small" round>已分享</n-tag>
              <n-tag v-else type="default" size="small" round>私有</n-tag>
            </div>
          </template>
          <template #header-extra>
            <n-text depth="3" size="small">{{ formatDate(ver.created_at) }}</n-text>
          </template>
          
          <div class="version-content">
            <n-text depth="3" v-if="!projectId && ver.project_name" class="project-tag">
              [{{ ver.project_name }}]
            </n-text>
            <div class="version-desc">{{ ver.description || '无描述' }}</div>
          </div>
          
          <template #action>
            <n-space justify="end" align="center">
              <n-switch :value="ver.is_shared" @update:value="(v) => toggleShare(ver, v)" size="small">
                <template #checked>公开</template>
                <template #unchecked>私有</template>
              </n-switch>
              
              <n-divider vertical />

              <n-button size="small" @click="editVersion(ver)">
                <template #icon><n-icon :component="CreateOutline" /></template>
                编辑
              </n-button>

              <n-button size="small" v-if="ver.is_shared" @click="copyLink(ver.id)">
                <template #icon><n-icon :component="CopyOutline" /></template>
                链接
              </n-button>
              
              <n-button size="small" v-if="ver.is_shared" type="info" @click="openLink(ver.id)">
                <template #icon><n-icon :component="PlayOutline" /></template>
                试玩
              </n-button>

              <n-popconfirm @positive-click="deleteVersion(ver.id)">
                <template #trigger>
                  <n-button size="small" type="error">
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
          <n-input v-model:value="formModel.title" placeholder="例如: v1.0, 测试版, 第一次修改..." />
        </n-form-item>
        <n-form-item label="描述 (可选)">
          <n-input v-model:value="formModel.description" type="textarea" placeholder="备注信息..." />
        </n-form-item>
        <n-form-item label="分享设置">
          <n-checkbox v-model:checked="formModel.is_shared">
            生成公开分享链接
          </n-checkbox>
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
import { NButton, NIcon, NCard, NEmpty, NTag, NSpace, NPopconfirm, NModal, NForm, NFormItem, NSelect, NInput, NSwitch, NDivider, NSpin, NCheckbox, NText, useMessage } from 'naive-ui';
import { ShareOutline, CopyOutline, PlayOutline, TrashOutline, SaveOutline, CreateOutline } from '@vicons/ionicons5';
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
  title: '',
  description: '',
  is_shared: false
});

const projectOptions = computed(() => {
  return projectStore.projects.map(p => ({ label: p, value: p }));
});

const canSubmit = computed(() => {
  if (isEditing.value) return !!formModel.value.title;
  return (props.projectId || formModel.value.projectName) && formModel.value.title;
});

async function loadVersions() {
  loading.value = true;
  try {
    let url = '/api/shares';
    const params = new URLSearchParams();
    if (props.projectId) params.append('project_name', props.projectId);
    else if (filterProject.value) params.append('project_name', filterProject.value);
    
    if (params.toString()) url += '?' + params.toString();

    const res = await fetchWithAuth(url);
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
    title: generateDefaultTitle(),
    description: '',
    is_shared: false
  };
  showModal.value = true;
}

function generateDefaultTitle() {
  const date = new Date();
  return `Backup ${date.getMonth()+1}/${date.getDate()} ${date.getHours()}:${date.getMinutes()}`;
}

function editVersion(ver) {
  isEditing.value = true;
  formModel.value = {
    id: ver.id,
    projectName: ver.project_name,
    title: ver.title,
    description: ver.description,
    is_shared: ver.is_shared
  };
  showModal.value = true;
}

async function submitForm() {
  submitting.value = true;
  try {
    if (isEditing.value) {
      // Update
      const res = await fetchWithAuth(`/api/shares/${formModel.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: formModel.value.title,
          description: formModel.value.description,
          is_shared: formModel.value.is_shared
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
      const res = await fetchWithAuth('/api/shares', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectName: props.projectId || formModel.value.projectName,
          title: formModel.value.title,
          description: formModel.value.description,
          is_shared: formModel.value.is_shared
        })
      });
      if (res.ok) {
        message.success('版本创建成功');
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
  // Optimistic update
  const oldVal = ver.is_shared;
  ver.is_shared = value;
  try {
    const res = await fetchWithAuth(`/api/shares/${ver.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_shared: value })
    });
    if (!res.ok) throw new Error();
    message.success(value ? '已设为公开' : '已设为私有');
  } catch (e) {
    ver.is_shared = oldVal;
    message.error('状态更新失败');
  }
}

async function deleteVersion(id) {
  try {
    const res = await fetchWithAuth(`/api/shares/${id}`, { method: 'DELETE' });
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

function copyLink(id) {
  const url = `${window.location.origin}/#/play/${id}`;
  navigator.clipboard.writeText(url).then(() => {
    message.success('链接已复制');
  });
}

function openLink(id) {
  const url = `/#/play/${id}`;
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

.project-tag {
  margin-right: 8px;
  font-weight: bold;
}

.version-desc {
  color: var(--n-text-color-3);
  font-size: 0.9em;
}
</style>

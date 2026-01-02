<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>管理中心 / Admin</h2>
      <div class="header-actions">
        <n-tag v-if="isAdmin" type="success" size="small">
          <template #icon>
            <n-icon><ShieldCheckmarkOutline /></n-icon>
          </template>
          管理员
        </n-tag>
        <n-button quaternary size="small" @click="refreshData">
          <template #icon>
            <n-icon><RefreshOutline /></n-icon>
          </template>
          刷新
        </n-button>
      </div>
    </div>
    
    <div class="content-area">
      <n-spin :show="loading">
        <div class="admin-container">
          <!-- 左栏：我的使用统计（所有人可见） -->
          <div class="admin-column">
            <n-card title="我的使用统计" size="small">
              <template #header-extra>
                <n-text depth="3">Token 用量</n-text>
              </template>
              
              <n-space vertical>
                <!-- 24小时统计 -->
                <n-statistic label="过去24小时">
                  <n-number-animation
                    :from="0"
                    :to="myUsage?.last_24h?.tokens || 0"
                    :precision="0"
                  />
                  <template #suffix>tokens</template>
                </n-statistic>
                
                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic label="请求次数" tabular-nums>
                      {{ myUsage?.last_24h?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="错误次数" tabular-nums>
                      <n-text :type="(myUsage?.last_24h?.errors || 0) > 0 ? 'error' : 'default'">
                        {{ myUsage?.last_24h?.errors || 0 }}
                      </n-text>
                    </n-statistic>
                  </n-gi>
                </n-grid>
                
                <n-divider />
                
                <!-- 历史累计统计 -->
                <n-statistic label="历史累计">
                  <n-number-animation
                    :from="0"
                    :to="myUsage?.total?.tokens || 0"
                    :precision="0"
                  />
                  <template #suffix>tokens</template>
                </n-statistic>
                
                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic label="总请求数" tabular-nums>
                      {{ myUsage?.total?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="总错误数" tabular-nums>
                      {{ myUsage?.total?.errors || 0 }}
                    </n-statistic>
                  </n-gi>
                </n-grid>
              </n-space>
            </n-card>
            
            <!-- 按模型统计 -->
            <n-card title="按模型统计" size="small" style="margin-top: 16px;">
              <n-data-table
                :columns="modelColumns"
                :data="myUsage?.by_model || []"
                :pagination="false"
                size="small"
                :max-height="300"
              />
            </n-card>
            
            <!-- 按Agent统计 -->
            <n-card title="按Agent统计" size="small" style="margin-top: 16px;">
              <n-data-table
                :columns="agentColumns"
                :data="myUsage?.by_agent || []"
                :pagination="false"
                size="small"
                :max-height="200"
              />
            </n-card>
          </div>
          
          <!-- 右栏：管理功能（仅管理员可见） -->
          <div class="admin-column" v-if="isAdmin">
            <!-- 用户管理 -->
            <n-card title="用户管理" size="small">
              <template #header-extra>
                <n-text depth="3">共 {{ allUsers.length }} 位用户</n-text>
              </template>
              
              <n-data-table
                :columns="userColumns"
                :data="allUsers"
                :pagination="{ pageSize: 10 }"
                size="small"
                :max-height="300"
              />
            </n-card>
            
            <!-- 系统平台限额配置 -->
            <n-card title="系统平台限额" size="small" style="margin-top: 16px;">
              <template #header-extra>
                <n-button size="tiny" type="primary" @click="showQuotaModal = true">
                  <template #icon>
                    <n-icon><AddOutline /></n-icon>
                  </template>
                  添加限额
                </n-button>
              </template>
              
              <n-alert type="info" style="margin-bottom: 12px;">
                限额仅对使用系统API Key的用户生效。用户自定义API Key时不受限制。
              </n-alert>
              
              <n-data-table
                :columns="quotaColumns"
                :data="quotaList"
                :pagination="false"
                size="small"
                :max-height="300"
              />
            </n-card>
            
            <!-- 全部用户使用概览 -->
            <n-card title="全部用户使用概览" size="small" style="margin-top: 16px;">
              <n-data-table
                :columns="allUsageColumns"
                :data="allUsersUsage"
                :pagination="{ pageSize: 10 }"
                size="small"
                :max-height="400"
              />
            </n-card>
          </div>
          
          <!-- 非管理员提示 -->
          <div class="admin-column" v-else>
            <n-card size="small">
              <n-empty description="管理功能需要管理员权限">
                <template #icon>
                  <n-icon size="48" color="#999">
                    <LockClosedOutline />
                  </n-icon>
                </template>
                <template #extra>
                  <n-text depth="3">
                    如需获取管理员权限，请联系系统管理员
                  </n-text>
                </template>
              </n-empty>
            </n-card>
          </div>
        </div>
      </n-spin>
    </div>
    
    <!-- 添加/编辑限额弹窗 -->
    <n-modal
      v-model:show="showQuotaModal"
      preset="dialog"
      title="设置系统平台限额"
      positive-text="保存"
      negative-text="取消"
      @positive-click="saveQuota"
      :loading="quotaSaving"
    >
      <n-form :model="quotaForm" label-placement="left" label-width="100">
        <n-form-item label="平台">
          <n-select
            v-model:value="quotaForm.platformId"
            :options="platformOptions"
            placeholder="选择系统平台"
            @update:value="onPlatformChange"
          />
        </n-form-item>
        
        <n-form-item label="模型">
          <n-select
            v-model:value="quotaForm.modelId"
            :options="modelOptions"
            placeholder="留空表示平台级限额"
            clearable
          />
        </n-form-item>
        
        <n-form-item label="限额类型">
          <n-radio-group v-model:value="quotaForm.quotaType">
            <n-radio-button value="unlimited">无限制</n-radio-button>
            <n-radio-button value="disabled">禁用</n-radio-button>
            <n-radio-button value="limited">限额</n-radio-button>
          </n-radio-group>
        </n-form-item>
        
        <n-form-item label="每日限额" v-if="quotaForm.quotaType === 'limited'">
          <n-input-number
            v-model:value="quotaForm.quotaValue"
            :min="1"
            :step="10000"
            placeholder="每日 token 限额"
            style="width: 100%"
          >
            <template #suffix>tokens/日</template>
          </n-input-number>
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue';
import {
  NCard, NButton, NIcon, NTag, NText, NStatistic, NNumberAnimation,
  NGrid, NGi, NDivider, NDataTable, NEmpty, NModal, NForm, NFormItem,
  NSelect, NRadioGroup, NRadioButton, NInputNumber, NSpace, NSpin,
  NAlert, NPopconfirm, useMessage
} from 'naive-ui';
import {
  ShieldCheckmarkOutline, RefreshOutline, AddOutline,
  LockClosedOutline, TrashOutline, CreateOutline
} from '@vicons/ionicons5';
import {
  getMyUsage, getAllUsers, getAllUsersUsage, getAllQuotas,
  setQuota, deleteQuota, setUserAdminStatus, formatTokens
} from '../services/adminService';
import { getUserInfo } from '../services/authService';

const message = useMessage();

// 状态
const loading = ref(false);
const isAdmin = ref(false);
const myUsage = ref(null);
const allUsers = ref([]);
const allUsersUsage = ref([]);
const quotaList = ref([]);
const systemPlatforms = ref([]);

// 限额表单
const showQuotaModal = ref(false);
const quotaSaving = ref(false);
const quotaForm = ref({
  platformId: null,
  modelId: null,
  quotaType: 'unlimited',
  quotaValue: 100000,
});

// 加载数据
async function refreshData() {
  loading.value = true;
  try {
    // 获取用户信息
    const userInfo = await getUserInfo();
    isAdmin.value = userInfo.is_admin || false;
    
    // 获取我的使用统计
    myUsage.value = await getMyUsage();
    
    // 如果是管理员，加载管理数据
    if (isAdmin.value) {
      const [users, usersUsage, quotasData] = await Promise.all([
        getAllUsers(),
        getAllUsersUsage(),
        getAllQuotas(),
      ]);
      
      allUsers.value = users;
      allUsersUsage.value = usersUsage;
      quotaList.value = quotasData.quotas || [];
      systemPlatforms.value = quotasData.system_platforms || [];
    }
  } catch (error) {
    message.error('加载数据失败: ' + error.message);
  } finally {
    loading.value = false;
  }
}

// 表格列定义
const modelColumns = [
  { title: '模型', key: 'display_name', ellipsis: true },
  { title: '平台', key: 'platform_name', width: 100 },
  { 
    title: 'Tokens', 
    key: 'total_tokens',
    width: 100,
    render: (row) => formatTokens(row.total_tokens || 0)
  },
  { title: '调用', key: 'call_count', width: 60 },
];

const agentColumns = [
  { title: 'Agent', key: 'agent_name', ellipsis: true },
  { 
    title: 'Tokens', 
    key: 'tokens',
    width: 100,
    render: (row) => formatTokens(row.tokens || 0)
  },
  { title: '调用', key: 'requests', width: 60 },
];

const userColumns = computed(() => [
  { title: 'ID', key: 'user_id', width: 50 },
  { title: '用户名', key: 'username', ellipsis: true },
  {
    title: '管理员',
    key: 'is_admin',
    width: 80,
    render: (row) => h(NTag, {
      type: row.is_admin ? 'success' : 'default',
      size: 'small',
    }, () => row.is_admin ? '是' : '否')
  },
  {
    title: '状态',
    key: 'is_active',
    width: 70,
    render: (row) => h(NTag, {
      type: row.is_active ? 'success' : 'error',
      size: 'small',
    }, () => row.is_active ? '正常' : '禁用')
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => h(NButton, {
      size: 'tiny',
      type: row.is_admin ? 'warning' : 'primary',
      onClick: () => toggleAdmin(row),
    }, () => row.is_admin ? '取消管理员' : '设为管理员')
  },
]);

const quotaColumns = computed(() => [
  { 
    title: '平台', 
    key: 'platform_id',
    render: (row) => {
      const platform = systemPlatforms.value.find(p => p.platform_id === row.platform_id);
      return platform?.platform_name || `平台 ${row.platform_id}`;
    }
  },
  { 
    title: '模型', 
    key: 'model_id',
    render: (row) => {
      if (!row.model_id) return h(NTag, { size: 'small' }, () => '平台级');
      const model = systemPlatforms.value.find(
        p => p.platform_id === row.platform_id && p.model_id === row.model_id
      );
      return model?.display_name || `模型 ${row.model_id}`;
    }
  },
  { 
    title: '限额',
    key: 'quota_value',
    render: (row) => {
      if (row.quota_value === -1) {
        return h(NTag, { type: 'success', size: 'small' }, () => '无限制');
      } else if (row.quota_value === 0) {
        return h(NTag, { type: 'error', size: 'small' }, () => '已禁用');
      } else {
        return h(NTag, { type: 'warning', size: 'small' }, () => formatTokens(row.quota_value) + '/日');
      }
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render: (row) => h(NPopconfirm, {
      onPositiveClick: () => removeQuota(row),
    }, {
      trigger: () => h(NButton, {
        size: 'tiny',
        type: 'error',
        quaternary: true,
      }, () => h(NIcon, null, () => h(TrashOutline))),
      default: () => '确定删除此限额配置？',
    })
  },
]);

const allUsageColumns = [
  { title: '用户', key: 'user.username', ellipsis: true },
  { 
    title: '24h Tokens',
    key: 'last_24h.tokens',
    render: (row) => formatTokens(row.last_24h?.tokens || 0)
  },
  { 
    title: '24h 请求',
    key: 'last_24h.requests',
    render: (row) => row.last_24h?.requests || 0
  },
  { 
    title: '累计 Tokens',
    key: 'total.tokens',
    render: (row) => formatTokens(row.total?.tokens || 0)
  },
  { 
    title: '累计请求',
    key: 'total.requests',
    render: (row) => row.total?.requests || 0
  },
];

// 平台选项
const platformOptions = computed(() => {
  const seen = new Set();
  return systemPlatforms.value
    .filter(p => {
      if (seen.has(p.platform_id)) return false;
      seen.add(p.platform_id);
      return true;
    })
    .map(p => ({
      label: p.platform_name,
      value: p.platform_id,
    }));
});

// 模型选项（根据选中的平台过滤）
const modelOptions = computed(() => {
  if (!quotaForm.value.platformId) return [];
  return systemPlatforms.value
    .filter(p => p.platform_id === quotaForm.value.platformId)
    .map(p => ({
      label: p.display_name,
      value: p.model_id,
    }));
});

function onPlatformChange() {
  quotaForm.value.modelId = null;
}

// 切换管理员状态
async function toggleAdmin(user) {
  try {
    await setUserAdminStatus(user.user_id, !user.is_admin);
    message.success('管理员状态已更新');
    await refreshData();
  } catch (error) {
    message.error(error.message);
  }
}

// 保存限额
async function saveQuota() {
  if (!quotaForm.value.platformId) {
    message.warning('请选择平台');
    return false;
  }
  
  let quotaValue;
  switch (quotaForm.value.quotaType) {
    case 'unlimited':
      quotaValue = -1;
      break;
    case 'disabled':
      quotaValue = 0;
      break;
    case 'limited':
      quotaValue = quotaForm.value.quotaValue || 100000;
      break;
  }
  
  quotaSaving.value = true;
  try {
    await setQuota(quotaForm.value.platformId, quotaForm.value.modelId, quotaValue);
    message.success('限额已保存');
    showQuotaModal.value = false;
    
    // 重置表单
    quotaForm.value = {
      platformId: null,
      modelId: null,
      quotaType: 'unlimited',
      quotaValue: 100000,
    };
    
    await refreshData();
    return true;
  } catch (error) {
    message.error(error.message);
    return false;
  } finally {
    quotaSaving.value = false;
  }
}

// 删除限额
async function removeQuota(quota) {
  try {
    await deleteQuota(quota.platform_id, quota.model_id);
    message.success('限额配置已删除');
    await refreshData();
  } catch (error) {
    message.error(error.message);
  }
}

onMounted(() => {
  refreshData();
});
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.panel-header {
  height: 50px;
  border-bottom: 1px solid var(--spark-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background-color: var(--spark-panel-bg);
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--spark-text);
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.admin-container {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 24px;
  max-width: 100%;
}

.admin-column {
  display: flex;
  flex-direction: column;
}

@media (max-width: 1200px) {
  .admin-container {
    grid-template-columns: 1fr;
  }
}
</style>
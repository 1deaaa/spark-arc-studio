
<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <h2 class="spark-desktop-title">管理中心 / Admin</h2>
        <p class="spark-desktop-subtitle">使用统计与系统管理</p>
      </div>
      <div class="header-actions spark-desktop-header__actions">
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
                <n-button-group size="tiny" class="spark-segment">
                  <n-button :type="usageRange === '24h' ? 'primary' : 'default'" @click="usageRange = '24h'; fetchMyUsageOnly()">24h</n-button>
                  <n-button :type="usageRange === '7d' ? 'primary' : 'default'" @click="usageRange = '7d'; fetchMyUsageOnly()">周</n-button>
                  <n-button :type="usageRange === '30d' ? 'primary' : 'default'" @click="usageRange = '30d'; fetchMyUsageOnly()">月</n-button>
                </n-button-group>
              </template>
              
              <n-space vertical>
                <n-statistic :label="usageRangeLabel">
                  {{ formatTokens(myUsage?.range_stats?.tokens || 0) }}
                  <template #suffix>tokens</template>
                </n-statistic>
                
                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic label="请求次数" tabular-nums>
                      {{ myUsage?.range_stats?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="错误次数" tabular-nums>
                      <n-text :type="(myUsage?.range_stats?.errors || 0) > 0 ? 'error' : 'default'">
                        {{ myUsage?.range_stats?.errors || 0 }}
                      </n-text>
                    </n-statistic>
                  </n-gi>
                </n-grid>
                
                <n-divider />
                
                <n-statistic label="历史累计">
                  {{ formatTokens(myUsage?.total?.tokens || 0) }}
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
            
            <n-card title="按模型统计" size="small" style="margin-top: 16px;">
              <n-data-table
                :columns="modelColumns"
                :data="myUsage?.by_model || []"
                :pagination="false"
                size="small"
                :max-height="300"
              />
            </n-card>
            
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

          <!-- 中栏：灵感信箱 -->
          <div class="admin-column">
             <MCPConnectCard />
          </div>
          
          <!-- 右栏：管理功能（仅管理员可见） -->
          <div class="admin-column" v-if="isAdmin">
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
import {
  NCard, NButton, NButtonGroup, NIcon, NTag, NText, NStatistic, 
  NGrid, NGi, NDivider, NDataTable, NModal, NForm, NFormItem,
  NSelect, NRadioGroup, NRadioButton, NInputNumber, NSpace, NSpin,
  NAlert, NPopconfirm
} from 'naive-ui';
import {
  ShieldCheckmarkOutline, RefreshOutline, AddOutline
} from '@vicons/ionicons5';
import MCPConnectCard from '../../components/settings/MCPConnectCard.vue';
import { useAdminLogic } from '../../composables/useAdminLogic';

const {
  loading,
  isAdmin,
  myUsage,
  usageRange,
  allUsers,
  allUsersUsage,
  quotaList,
  showQuotaModal,
  quotaSaving,
  quotaForm,
  usageRangeLabel,
  refreshData,
  fetchMyUsageOnly,
  modelColumns,
  agentColumns,
  userColumns,
  quotaColumns,
  allUsageColumns,
  platformOptions,
  modelOptions,
  onPlatformChange,
  saveQuota
} = useAdminLogic();

function formatTokens(value) {
  const num = Number(value) || 0;
  if (num >= 1_000_000) {
    const v = (num / 1_000_000).toFixed(1).replace(/\.0$/, '');
    return `${v}M`;
  }
  if (num >= 1_000) {
    const v = (num / 1_000).toFixed(1).replace(/\.0$/, '');
    return `${v}K`;
  }
  return `${num}`;
}
</script>

<style scoped>
.view-container {
  height: 100%;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content-area {
  flex: 1;
  /* 布局修复：防止无内容时宽度坍缩 */
  width: 100%;
  min-width: 0;
  overflow-y: auto;
  padding: 20px;
}

.admin-container {
  display: grid;
  grid-template-columns: 0.74fr 1.06fr 1fr;
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

.spark-anim-fade {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>

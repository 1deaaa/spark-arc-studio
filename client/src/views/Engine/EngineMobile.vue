<template>
  <div class="engine-mobile">
    <div class="mobile-section">
      <h3 class="section-title">
        <n-icon :component="GameControllerOutline" />
        引擎绑定
      </h3>
      <p class="section-desc">连接游戏引擎与 Agent 模型配置</p>
    </div>
    
    <!-- Agent 模型配置 -->
    <AgentModelCard />
    
    <!-- 状态展示 -->
    <div class="status-section">
      <h4 class="status-title">连接状态</h4>
      <div class="status-list">
        <div class="status-item">
          <span class="status-label">Unity 引擎</span>
          <n-tag :type="unityConnected ? 'success' : 'default'" size="small">
            {{ unityConnected ? '已连接' : '未连接' }}
          </n-tag>
        </div>
        <div class="status-item">
          <span class="status-label">Agent 服务</span>
          <n-tag type="success" size="small">运行中</n-tag>
        </div>
        <div class="status-item">
          <span class="status-label">已配置函数</span>
          <span class="status-value">{{ bindingCount }} 个</span>
        </div>
      </div>
    </div>

    <!-- MCP 配置 -->
    <div class="mcp-section">
      <MCPConnectCard />
    </div>
    
        <!-- 桌面端引导 -->
    <div class="desktop-cta">
      <div class="cta-left">
        <n-icon :component="DesktopOutline" size="24" class="cta-icon-small" />
        <div class="cta-text">
          <h4>完整编辑请前往桌面端</h4>
          <p>复杂的大语言模型 Flow 编排需在电脑上进行</p>
        </div>
      </div>
      <n-button size="small" type="primary" ghost @click="copyDesktopUrl">
        复制链接
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { NIcon, NTag, NButton, useMessage } from 'naive-ui';
import { 
  GameControllerOutline, 
  DesktopOutline,
  CopyOutline
} from '@vicons/ionicons5';
import MCPConnectCard from '../../components/settings/MCPConnectCard.vue';
import AgentModelCard from '../../components/settings/AgentModelCard.vue';

const message = useMessage();

// 模拟状态数据
const unityConnected = ref(false);
const bindingCount = ref(0);

function copyDesktopUrl() {
  const url = window.location.origin + window.location.pathname;
  navigator.clipboard.writeText(url).then(() => {
    message.success('链接已复制，请在电脑浏览器中打开');
  }).catch(() => {
    message.error('复制失败');
  });
}
</script>

<style scoped>
.engine-mobile {
  padding: 0 4px;
}

.mobile-section {
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--spark-primary);
  margin: 0 0 8px 0;
}

.section-desc {
  font-size: 13px;
  color: var(--spark-text-muted);
  margin: 0;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.feature-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px 12px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  text-align: center;
}

.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, 
    rgba(var(--spark-primary-rgb), 0.15),
    rgba(var(--spark-primary-rgb), 0.08)
  );
  color: var(--spark-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-text);
}

.feature-desc {
  font-size: 12px;
  color: var(--spark-text-muted);
  margin-top: 2px;
}

.status-section {
  margin-bottom: 24px;
}

.status-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--spark-text-muted);
  margin: 0 0 12px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-list {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  overflow: hidden;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px;
  border-bottom: 1px solid var(--spark-border);
}

.status-item:last-child {
  border-bottom: none;
}

.status-label {
  font-size: 14px;
  color: var(--spark-text);
}

.status-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--spark-primary);
}

.mcp-section {
  margin-bottom: 24px;
}

.desktop-cta {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(var(--spark-primary-rgb), 0.05);
  border: 1px dashed rgba(var(--spark-primary-rgb), 0.3);
  border-radius: 12px;
  margin-top: 10px;
}

.cta-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cta-icon-small {
  color: var(--spark-primary);
}

.cta-text h4 {
  margin: 0 0 2px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--spark-text);
}

.cta-text p {
  margin: 0;
  font-size: 11px;
  color: var(--spark-text-muted);
}
</style>

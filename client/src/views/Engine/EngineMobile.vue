<template>
  <div class="engine-mobile">
    <div class="mobile-section">
      <h3 class="section-title">
        <n-icon :component="GameControllerOutline" />
        引擎绑定
      </h3>
      <p class="section-desc">连接游戏引擎与 Agent 函数映射</p>
    </div>
    
    <!-- 功能概览 -->
    <div class="feature-grid">
      <div class="feature-card">
        <div class="feature-icon">
          <n-icon :component="GitBranchOutline" size="24" />
        </div>
        <div class="feature-text">
          <div class="feature-title">Agent Flow</div>
          <div class="feature-desc">可视化编排 AI 工作流</div>
        </div>
      </div>
      
      <div class="feature-card">
        <div class="feature-icon">
          <n-icon :component="CodeSlashOutline" size="24" />
        </div>
        <div class="feature-text">
          <div class="feature-title">函数映射</div>
          <div class="feature-desc">绑定引擎函数调用</div>
        </div>
      </div>
    </div>
    
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
    
    <!-- 桌面端引导 -->
    <div class="desktop-cta">
      <div class="cta-icon">
        <n-icon :component="DesktopOutline" size="32" />
      </div>
      <h4>完整编辑需要桌面端</h4>
      <p>Agent Flow 编排和函数绑定涉及复杂的可视化操作，请在电脑端进行配置。</p>
      <n-button type="primary" ghost @click="copyDesktopUrl">
        <template #icon><n-icon :component="CopyOutline" /></template>
        复制桌面端链接
      </n-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NIcon, NTag, NButton, useMessage } from 'naive-ui';
import { 
  GameControllerOutline, 
  GitBranchOutline, 
  CodeSlashOutline,
  DesktopOutline,
  CopyOutline
} from '@vicons/ionicons5';

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

.desktop-cta {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 28px 20px;
  background: linear-gradient(135deg, 
    rgba(var(--spark-primary-rgb), 0.08),
    rgba(var(--spark-secondary-rgb), 0.05)
  );
  border: 1px dashed rgba(var(--spark-primary-rgb), 0.3);
  border-radius: 16px;
}

.cta-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: var(--spark-panel-bg);
  color: var(--spark-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.desktop-cta h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--spark-text);
}

.desktop-cta p {
  margin: 0 0 16px 0;
  font-size: 13px;
  color: var(--spark-text-muted);
  line-height: 1.5;
}
</style>

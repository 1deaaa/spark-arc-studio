<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Genesis / 世界观构建</h2>
      <div class="toolbar">
        <n-radio-group v-model:value="activeTab" size="small">
          <n-radio-button value="lorebook">Lorebook (设定集)</n-radio-button>
          <n-radio-button value="characters">Characters (角色生成)</n-radio-button>
          <n-radio-button value="ai-settings">AI Settings (模型配置)</n-radio-button>
        </n-radio-group>
      </div>
    </div>
    
    <div class="content-area">
      <div v-show="activeTab === 'lorebook'" class="tab-content">
        <LorebookEditor :visible="true" :embedded="true" />
      </div>
      
      <div v-show="activeTab === 'characters'" class="tab-content">
        <CharacterGeneratorPanel :visible="true" :embedded="true" />
      </div>

      <div v-show="activeTab === 'ai-settings'" class="tab-content">
        <AiSettingsPanel :visible="true" :embedded="true" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NRadioGroup, NRadioButton } from 'naive-ui';
import LorebookEditor from '../components/lorebook/LorebookEditor.vue';
import CharacterGeneratorPanel from '../components/lorebook/CharacterGeneratorPanel.vue';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';

const activeTab = ref('lorebook');
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

.content-area {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.tab-content {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

/* Adjust embedded components if necessary */
:deep(.n-card) {
  background: transparent;
}
</style>

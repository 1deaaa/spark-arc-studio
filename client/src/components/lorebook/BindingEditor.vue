<template>
  <div class="binding-editor-container">
    <n-space vertical :size="16">
      <!-- 行为函数绑定 -->
      <n-card 
        :segmented="{ content: true }"
        :bordered="false"
        size="small"
      >
        <template #header>
          <n-space align="center" :size="4">
            <span>行为函数绑定 (Unity)</span>
            <n-tooltip trigger="hover" placement="right">
              <template #trigger>
                <n-icon :component="Info" size="16" style="cursor: pointer; opacity: 0.6; display: flex;" />
              </template>
              配置对话中的 act 行为节点与 Unity C# 函数的映射关系
            </n-tooltip>
          </n-space>
        </template>
        <template #header-extra>
          <n-space align="center" :size="8">
            <input
              ref="manifestInputRef"
              type="file"
              accept=".json,application/json"
              style="display: none"
              @change="importActionManifest"
            />
            <n-tooltip trigger="hover" placement="top" style="max-width: 320px">
              <template #trigger>
                <n-icon :component="Info" size="16" style="cursor: pointer; opacity: 0.6; display: flex;" />
              </template>
              导入由 Unity 编辑器导出的行为清单 JSON 文件（在 Unity 菜单中执行 SparkArc -> Actions -> Export Action Manifest 导出）。这能够将 C# 代码中带有 [SparkArcAction] 标记的 Handler 方法自动同步到此处，省去手动创建映射的步骤。
            </n-tooltip>
            <n-button size="small" secondary strong @click="openManifestPicker">
              <template #icon>
                <n-icon :component="Upload" />
              </template>
              {{ t('components.bindingEditor.importUnityManifest') }}
            </n-button>
            <n-icon :component="Code" size="20" />
          </n-space>
        </template>

        <n-space vertical :size="12">
          <!-- 添加行为绑定 -->
          <n-collapse>
            <n-collapse-item title="添加新的行为函数" name="add-act">
              <n-form label-placement="left" label-width="100">
                <n-form-item label="行为名称">
                  <n-input 
                    v-model:value="newActName" 
                    placeholder="例如: bgm (播放背景音乐)"
                    clearable
                  />
                </n-form-item>
                <n-form-item label="Unity函数名">
                  <n-input 
                    v-model:value="newActFuncName" 
                    placeholder="例如: PlayBGM (C# 方法名)"
                    clearable
                  />
                </n-form-item>
                <n-form-item label="函数类型">
                  <n-input 
                    v-model:value="newActType" 
                    placeholder="例如: audio (可选，用于分类)"
                    clearable
                  />
                </n-form-item>
                <n-form-item label="描述">
                  <n-input 
                    v-model:value="newActDescription" 
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    placeholder="例如: 播放指定的背景音乐，第一个参数是音乐名称，第二个参数是音量(0-1)"
                  />
                </n-form-item>
                <n-form-item label="参数示例">
                  <n-input 
                    v-model:value="newActArgsStr" 
                    type="textarea"
                    :autosize="{ minRows: 3, maxRows: 6 }"
                    :placeholder='`{\n  "bgm_name": ["battle_theme", "town_theme", "boss_theme"],\n  "volume": 0.8,\n  "fade_duration": 2.0\n}`'
                  />
                </n-form-item>
                <n-button type="primary" @click="addActionBinding" block strong>
                  <template #icon>
                    <n-icon :component="Plus" />
                  </template>
                  添加行为函数
                </n-button>
              </n-form>
            </n-collapse-item>
          </n-collapse>

          <!-- 行为绑定列表 -->
          <n-collapse>
            <n-collapse-item 
              v-for="act in actionBindings" 
              :key="act.id" 
              :title="`${act.act_name} → ${act.func_name}`"
              :name="String(act.id)"
            >
              <n-form label-placement="left" label-width="100" size="small">
                <n-form-item label="行为名称">
                  <n-input v-model:value="act.act_name" @blur="updateActionBinding(act)" />
                </n-form-item>
                <n-form-item label="Unity函数">
                  <n-input v-model:value="act.func_name" @blur="updateActionBinding(act)" />
                </n-form-item>
                <n-form-item label="类型">
                  <n-input v-model:value="act.act_type" @blur="updateActionBinding(act)" />
                </n-form-item>
                <n-form-item label="Handler">
                  <n-input v-model:value="act.handler_type" @blur="updateActionBinding(act)" />
                </n-form-item>
                <n-form-item label="描述">
                  <n-input 
                    v-model:value="act.act_description" 
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    @blur="updateActionBinding(act)"
                  />
                </n-form-item>
                <n-form-item label="参数示例">
                  <n-input 
                    v-model:value="act.act_args_str" 
                    type="textarea"
                    :autosize="{ minRows: 3, maxRows: 6 }"
                    @blur="updateActionBindingArgs(act)"
                  />
                </n-form-item>
                <n-button 
                  type="error" 
                  @click="deleteActionBinding(act.id)" 
                  block
                >
                  <template #icon>
                    <n-icon :component="Trash" />
                  </template>
                  删除此行为函数
                </n-button>
              </n-form>
            </n-collapse-item>
          </n-collapse>

          <n-empty v-if="actionBindings.length === 0" description="暂无行为函数绑定" />
        </n-space>
      </n-card>

      <!-- 全局注册表 -->
      <n-card 
        :segmented="{ content: true }"
        :bordered="false"
        size="small"
      >
        <template #header>
          <n-space align="center" :size="4">
            <span>全局注册表 (Unity)</span>
            <n-tooltip trigger="hover" placement="right">
              <template #trigger>
                <n-icon :component="Info" size="16" style="cursor: pointer; opacity: 0.6; display: flex;" />
              </template>
              注册全局变量和枚举列表，可在对话中用 {"{name}"} 占位符引用
            </n-tooltip>
          </n-space>
        </template>
        <template #header-extra>
          <n-icon :component="List" size="20" />
        </template>

        <n-space vertical :size="12">
          <!-- 添加注册项 -->
          <n-collapse>
            <n-collapse-item title="添加新的注册项" name="add-reg">
              <n-form label-placement="left" label-width="100">
                <n-form-item label="变量名">
                  <n-input 
                    v-model:value="newRegName" 
                    placeholder="例如: player_name (对话中用 {player_name} 引用)"
                    clearable
                  />
                </n-form-item>
                <n-form-item label="值 (JSON)">
                  <n-input 
                    v-model:value="newRegValueStr" 
                    type="textarea"
                    :autosize="{ minRows: 3, maxRows: 8 }"
                    :placeholder='`[\n  "沃森区",\n  "太平洲",\n  "狗镇"\n]`'
                  />
                </n-form-item>
                <n-button type="primary" @click="addRegistry" block strong>
                  <template #icon>
                    <n-icon :component="Plus" />
                  </template>
                  添加注册项
                </n-button>
              </n-form>
            </n-collapse-item>
          </n-collapse>

          <!-- 注册表列表 -->
          <n-collapse>
            <n-collapse-item 
              v-for="reg in registries" 
              :key="reg.id" 
              :title="`{${reg.name}}`"
              :name="String(reg.id)"
            >
              <n-form label-placement="left" label-width="100" size="small">
                <n-form-item label="变量名">
                  <n-input v-model:value="reg.name" @blur="updateRegistry(reg)" />
                </n-form-item>
                <n-form-item label="值 (JSON)">
                  <n-input 
                    v-model:value="reg.value_str" 
                    type="textarea"
                    :autosize="{ minRows: 3, maxRows: 8 }"
                    @blur="updateRegistryValue(reg)"
                  />
                </n-form-item>
                <n-button 
                  type="error" 
                  @click="deleteRegistry(reg.id)" 
                  block
                >
                  <template #icon>
                    <n-icon :component="Trash" />
                  </template>
                  删除此注册项
                </n-button>
              </n-form>
            </n-collapse-item>
          </n-collapse>

          <n-empty v-if="registries.length === 0" description="暂无注册项" />
        </n-space>
      </n-card>
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';
import {
  NCard, NSpace, NInput, NButton, NIcon,
  NCollapse, NCollapseItem, NForm, NFormItem, NEmpty, NTooltip
} from 'naive-ui';
import SparkAlert from '@/components/share/SparkAlert.vue';
import { Code, List, Plus, Trash, Upload, Info } from '@lucide/vue';
import { useProjectStore } from '@/components/stores/projectStore';
import { useActionBindingStore } from '@/components/stores/actionBindingStore';
import bus from '@/eventBus';

const projectStore = useProjectStore();
const actionBindingStore = useActionBindingStore();
const { actionBindings, registries } = storeToRefs(actionBindingStore);
const { t } = useI18n();

// 行为函数绑定
const newActName = ref('');
const newActFuncName = ref('');
const newActType = ref('');
const newActDescription = ref('');
const newActArgsStr = ref('');
const manifestInputRef = ref<HTMLInputElement | null>(null);

// 全局注册表
const newRegName = ref('');
const newRegValueStr = ref('');

// 加载数据
async function loadAllBindings() {
  try {
    await actionBindingStore.load(projectStore.currentProject, true);
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    bus.emit('toast', { type: 'error', message: `加载绑定数据失败: ${errorMessage}` });
  }
}

// 行为函数绑定操作
function addActionBinding() {
  if (!newActName.value.trim() || !newActFuncName.value.trim()) {
    bus.emit('toast', { type: 'warning', message: '请填写行为名称和Unity函数名' });
    return;
  }
  
  let argsObj = {};
  try {
    argsObj = JSON.parse(newActArgsStr.value || '{}');
  } catch {
    bus.emit('toast', { type: 'warning', message: '参数示例JSON格式错误，已使用空对象' });
  }
  
  actionBindings.value.push({
    id: Date.now(),
    act_name: newActName.value.trim(),
    func_name: newActFuncName.value.trim(),
    handler_type: null,
    act_type: newActType.value.trim() || null,
    act_description: newActDescription.value.trim() || null,
    act_args: argsObj,
    act_args_str: JSON.stringify(argsObj, null, 2)
  });
  
  newActName.value = '';
  newActFuncName.value = '';
  newActType.value = '';
  newActDescription.value = '';
  newActArgsStr.value = '';
  
  saveAllActionBindings();
}

function openManifestPicker() {
  manifestInputRef.value?.click();
}

async function importActionManifest(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;

  try {
    const manifest = JSON.parse(await file.text());
    const actions = Array.isArray(manifest?.actions) ? manifest.actions : [];
    if (!actions.length) {
      bus.emit('toast', { type: 'warning', message: t('components.bindingEditor.emptyManifest') });
      return;
    }

    let imported = 0;
    for (const item of actions) {
      const actName = String(item?.act_name || '').trim();
      const funcName = String(item?.func_name || '').trim();
      if (!actName || !funcName) continue;

      const existing = actionBindings.value.find((act) => act.act_name === actName);
      const actArgs = normalizeManifestArgs(item?.act_args);
      const payload = {
        id: existing?.id ?? `manifest-${actName}`,
        act_name: actName,
        func_name: funcName,
        handler_type: item?.handler_type == null ? null : String(item.handler_type),
        act_type: item?.act_type == null ? null : String(item.act_type),
        act_description: item?.act_description == null ? null : String(item.act_description),
        act_args: actArgs,
        act_args_str: JSON.stringify(actArgs, null, 2),
      };

      if (existing) {
        Object.assign(existing, payload);
      } else {
        actionBindings.value.push(payload);
      }
      imported += 1;
    }

    await saveAllActionBindings();
    bus.emit('toast', { type: 'success', message: t('components.bindingEditor.importedManifest', { count: imported }) });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    bus.emit('toast', { type: 'error', message: t('components.bindingEditor.importManifestFailed', { message: errorMessage }) });
  }
}

function normalizeManifestArgs(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function updateActionBinding(act) {
  saveAllActionBindings();
}

function updateActionBindingArgs(act) {
  try {
    act.act_args = JSON.parse(act.act_args_str || '{}');
    saveAllActionBindings();
  } catch {
    bus.emit('toast', { type: 'error', message: '参数JSON格式错误' });
  }
}

function deleteActionBinding(id) {
  actionBindings.value = actionBindings.value.filter(a => a.id !== id);
  saveAllActionBindings();
}

async function saveAllActionBindings() {
  if (!projectStore.currentProject) return;
  
  try {
    await actionBindingStore.saveActionBindingsForProject(projectStore.currentProject);
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    bus.emit('toast', { type: 'error', message: `保存失败: ${errorMessage}` });
  }
}

// 全局注册表操作
function addRegistry() {
  if (!newRegName.value.trim()) {
    bus.emit('toast', { type: 'warning', message: '请填写变量名' });
    return;
  }
  
  let valueArr = [];
  try {
    valueArr = JSON.parse(newRegValueStr.value || '[]');
  } catch {
    bus.emit('toast', { type: 'warning', message: '值JSON格式错误，已使用空数组' });
  }
  
  registries.value.push({
    id: Date.now(),
    name: newRegName.value.trim(),
    value: valueArr,
    value_str: JSON.stringify(valueArr, null, 2)
  });
  
  newRegName.value = '';
  newRegValueStr.value = '';
  
  saveAllRegistries();
}

function updateRegistry(reg) {
  saveAllRegistries();
}

function updateRegistryValue(reg) {
  try {
    reg.value = JSON.parse(reg.value_str || '[]');
    saveAllRegistries();
  } catch {
    bus.emit('toast', { type: 'error', message: '值JSON格式错误' });
  }
}

function deleteRegistry(id) {
  registries.value = registries.value.filter(r => r.id !== id);
  saveAllRegistries();
}

async function saveAllRegistries() {
  if (!projectStore.currentProject) return;
  
  try {
    await actionBindingStore.saveRegistriesForProject(projectStore.currentProject);
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    bus.emit('toast', { type: 'error', message: `保存失败: ${errorMessage}` });
  }
}

onMounted(() => {
  loadAllBindings();
});

watch(() => projectStore.currentProject, () => {
  loadAllBindings();
});
</script>

<style scoped>
.binding-editor-container {
  padding-bottom: var(--spark-panel-padding);
  max-width: 1200px;
  margin: 0 auto;
}
</style>

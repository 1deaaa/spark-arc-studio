<template>
  <div class="binding-editor-container">
    <n-alert type="info" style="margin-bottom: 16px" :bordered="false" closable>
      <strong>提示：</strong>角色绑定会在导出 SQLite 时自动同步到数据库，无需手动配置。
      <br/>请在"世界观&角色"标签页中管理角色，导出时会自动将角色 ID 和名称写入 binding_chr 表。
    </n-alert>

    <n-collapse style="margin-bottom: 16px">
      <n-collapse-item title="💡 完整使用示例" name="example">
        <n-card size="small">
          <strong>1. 在剧本中编写对话：</strong>
          <pre style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 4px; margin: 8px 0; overflow-x: auto;"><code>{
  "id": 10001,
  "chr": 0,
  "txt": "欢迎来到{player_name}的冒险之旅！",
  "act": {
    "bgm": "town_theme",
    "weather": ["sunny", "12h", "{place}"]
  }
}</code></pre>

          <strong>2. 配置行为函数绑定：</strong>
          <ul style="margin: 8px 0;">
            <li><code>bgm</code> → <code>PlayBGM(string musicName)</code></li>
            <li><code>weather</code> → <code>ChangeWeather(string type, string duration, string location)</code></li>
          </ul>

          <strong>3. 配置全局注册表：</strong>
          <ul style="margin: 8px 0;">
            <li><code>player_name</code> = <code>["艾莉"]</code></li>
            <li><code>place</code> = <code>["沃森区", "太平洲", "狗镇"]</code></li>
          </ul>

          <strong>4. Unity C# 实现示例：</strong>
          <pre style="background: rgba(128,128,128,0.1); padding: 12px; border-radius: 4px; margin: 8px 0; overflow-x: auto;"><code>// 从数据库读取行为绑定
var actBinding = db.Query&lt;BindAct&gt;("SELECT * FROM binding_act WHERE act_name = 'bgm'");
// 调用：PlayBGM("town_theme")

// 替换占位符
var registry = db.Query&lt;Registry&gt;("SELECT * FROM registry WHERE name = 'player_name'");
string text = dialogue.txt.Replace("{player_name}", registry.value[0]);
// 结果："欢迎来到艾莉的冒险之旅！"</code></pre>
        </n-card>
      </n-collapse-item>
    </n-collapse>

    <n-space vertical :size="16">
      <!-- 行为函数绑定 -->
      <n-card 
        title="行为函数绑定 (Unity)" 
        :segmented="{ content: true }"
        :bordered="false"
        size="small"
      >
        <template #header-extra>
          <n-icon :component="CodeSlashOutline" size="20" />
        </template>

        <n-alert type="info" style="margin-bottom: 12px" :bordered="false">
          配置对话中的 act 行为节点与 Unity C# 函数的映射关系
        </n-alert>

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
                    <n-icon :component="AddOutline" />
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
                    <n-icon :component="TrashOutline" />
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
        title="全局注册表 (Unity)" 
        :segmented="{ content: true }"
        :bordered="false"
        size="small"
      >
        <template #header-extra>
          <n-icon :component="ListOutline" size="20" />
        </template>

        <n-alert type="info" style="margin-bottom: 12px" :bordered="false">
          注册全局变量和枚举列表，可在对话中用 {"{name}"} 占位符引用
        </n-alert>

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
                    <n-icon :component="AddOutline" />
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
                    <n-icon :component="TrashOutline" />
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
import { 
  NCard, NSpace, NInput, NInputGroup, NInputNumber, NButton, NIcon, NTable, 
  NTag, NAlert, NCollapse, NCollapseItem, NForm, NFormItem, NEmpty
} from 'naive-ui';
import { 
  CodeSlashOutline, ListOutline, AddOutline, 
  SaveOutline, TrashOutline 
} from '@vicons/ionicons5';
import { useProjectStore } from '@/components/stores/projectStore';
import { 
  fetchActionBindings, saveActionBindings, 
  fetchRegistries, saveRegistries 
} from '@/services/api';
import bus from '@/eventBus';

const projectStore = useProjectStore();

// 行为函数绑定
const actionBindings = ref([]);
const newActName = ref('');
const newActFuncName = ref('');
const newActType = ref('');
const newActDescription = ref('');
const newActArgsStr = ref('');

// 全局注册表
const registries = ref([]);
const newRegName = ref('');
const newRegValueStr = ref('');

// 加载数据
async function loadAllBindings() {
  if (!projectStore.currentProject) return;
  
  try {
    const [actData, regData] = await Promise.all([
      fetchActionBindings(projectStore.currentProject),
      fetchRegistries(projectStore.currentProject)
    ]);
    
    actionBindings.value = (actData || []).map(act => ({
      ...act,
      act_args_str: JSON.stringify(act.act_args || {}, null, 2)
    }));
    
    registries.value = (regData || []).map(reg => ({
      ...reg,
      value_str: JSON.stringify(reg.value || [], null, 2)
    }));
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
    const dataToSave = actionBindings.value.map(act => ({
      id: act.id,
      act_name: act.act_name,
      func_name: act.func_name,
      act_type: act.act_type,
      act_description: act.act_description,
      act_args: act.act_args
    }));
    
    await saveActionBindings(projectStore.currentProject, dataToSave);
    bus.emit('toast', { type: 'success', message: '行为函数绑定保存成功' });
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
    const dataToSave = registries.value.map(reg => ({
      id: reg.id,
      name: reg.name,
      value: reg.value
    }));
    
    await saveRegistries(projectStore.currentProject, dataToSave);
    bus.emit('toast', { type: 'success', message: '注册表保存成功' });
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
  padding: var(--spark-panel-padding);
  max-width: 1200px;
  margin: 0 auto;
}
</style>

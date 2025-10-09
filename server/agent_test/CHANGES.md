# 风格提取系统改进说明

## 改进日期
2025年10月9日

## 问题描述
原系统在LLM返回JSON格式不完美时会解析失败，导致整个流程中断。常见错误包括：
- JSON格式错误（缺少引号、多余逗号等）
- 网络连接中断（httpx.RemoteProtocolError）
- 响应过长导致截断

## 改进方案

### 1. 放宽JSON解析限制
**改动文件**: `agent_style.py`

#### 改动1: 文件格式改为txt
- **原**: 保存为 `.json` 文件，严格验证JSON格式
- **新**: 保存为 `.txt` 文件，保留JSON格式但不强制验证
- **优势**: 即使JSON格式有小瑕疵也能正常保存和使用

```python
# 修改前
def get_style_filepath(author_id: str) -> Path:
   return STYLE_FILES_PATH / f"{author_id}.json"

# 修改后
def get_style_filepath(author_id: str) -> Path:
   return STYLE_FILES_PATH / f"{author_id}.txt"
```

#### 改动2: 风格提取函数不再强制解析JSON
```python
# 修改前
try:
    return json.loads(content)  # 解析失败则返回None
except json.JSONDecodeError as e:
    print(f"JSON解析失败: {e}")
    return None

# 修改后
print(f"✓ 风格分析完成 (内容长度: {len(content)} 字符)")
return content  # 直接返回字符串，不做JSON验证
```

#### 改动3: 加载函数返回字符串
```python
# 修改前
def load_style_profile_from_file(author_id: str) -> dict | None:
   with open(filepath, 'r', encoding='utf-8') as f:
       return json.load(f)  # 返回字典

# 修改后
def load_style_profile_from_file(author_id: str) -> str | None:
   with open(filepath, 'r', encoding='utf-8') as f:
       return f.read()  # 返回字符串
```

#### 改动4: 续写函数兼容两种格式
```python
# 尝试解析为JSON以提取特定字段（如果失败就使用完整字符串）
try:
    style_data = json.loads(style_data_str)
    is_json_valid = True
except:
    is_json_valid = False
    print("风格数据非标准JSON格式，将使用完整内容")

# 如果是标准JSON，可以提取特定维度
# 如果不是，就使用完整内容
```

### 2. 添加重试机制
**改动文件**: `agent_style.py`

#### 改动1: 导入time模块
```python
import time
```

#### 改动2: LLM调用添加重试逻辑
```python
max_retries = 3
retry_delay = 5  # 秒

for attempt in range(max_retries):
    try:
        print(f"正在调用LLM... (尝试 {attempt + 1}/{max_retries})")
        response = llm.invoke(prompt)
        # ... 成功处理
        return content
        
    except Exception as e:
        print(f"✗ 第 {attempt + 1} 次尝试失败: {str(e)[:100]}")
        
        if attempt < max_retries - 1:
            print(f"等待 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)
        else:
            print(f"✗ 所有重试均失败，放弃提取风格")
            return None
```

### 3. 优化文本长度限制
**改动文件**: `agent_style.py`

```python
# 修改前
if len(full_text) > 30000:
    sample_text = full_text[:80000]  # 错误：限制30000但取80000

# 修改后
max_chars = 30000  # 约10k-15k tokens
if len(full_text) > max_chars:
    sample_text = full_text[:max_chars]  # 正确
```

### 4. 增强错误处理
**改动文件**: `test_full_chapters.py`

#### 改动1: 风格提取添加try-catch
```python
try:
    author_style = save_style_profile("author_yoru_otsuichi", chapters)
except Exception as e:
    print(f"\n✗ 风格提取过程出错: {e}")
    traceback.print_exc()
    author_style = None
```

#### 改动2: 兼容字符串格式
```python
# 因为author_style现在是字符串，需要先尝试解析
try:
    style_dict = json.loads(author_style)
    # 可以统计维度
except:
    # 使用字符串长度代替
    print(f"✓ 风格档案已保存 (长度: {len(author_style):,} 字符)")
```

#### 改动3: 续写测试添加错误处理
```python
try:
    llm = AIManager().get_user_llm()
    response = llm.invoke(prompt)
    print("   ✓ 生成完成")
except Exception as e:
    print(f"   ✗ LLM调用失败: {e}")
    response = None
```

## 改进效果

### 优势
✅ **容错性强**: JSON格式小问题不会导致系统崩溃  
✅ **重试机制**: 网络波动时自动重试，提高成功率  
✅ **向后兼容**: 标准JSON仍可正常解析和使用特定字段  
✅ **错误追踪**: 详细的错误信息便于调试  
✅ **稳定性高**: 多层保护，每个环节都有错误处理

### 使用场景
1. **标准JSON**: 可以提取特定维度（dialogue、monologue等）
2. **非标准JSON**: 直接使用完整内容，仍能保持风格指导
3. **网络中断**: 自动重试，降低失败概率
4. **超长文本**: 自动截断到合理长度

## 测试建议

### 测试1: 正常流程
```bash
python test_full_chapters.py
```
预期：成功提取风格并生成续写

### 测试2: 网络波动
在网络不稳定环境下运行，观察重试机制

### 测试3: 格式验证
检查生成的 `author_styles/author_yoru_otsuichi.txt` 文件，验证内容完整性

## 文件结构
```
server/agent_test/
├── agent_style.py          # 核心功能（已改进）
├── test_full_chapters.py   # 测试脚本（已改进）
├── author_styles/          # 风格文件目录
│   └── *.txt              # 风格数据文件（新格式）
├── author_style_db/        # 向量库目录
└── CHANGES.md             # 本说明文档
```

## 迁移指南

如果已有旧的 `.json` 风格文件，无需特殊处理：
1. 系统会优先读取 `.txt` 文件
2. 如需转换，只需重命名 `.json` → `.txt`
3. 内容格式不需要修改

## 注意事项

⚠️ **重要**: 虽然放宽了JSON验证，但仍建议LLM返回标准JSON格式以便：
- 提取特定维度（dialogue/monologue/narrative）
- 更精细的风格控制
- 更好的可读性和维护性

⚠️ **Token限制**: 当前限制为30000字符（约10k-15k tokens），可根据模型调整

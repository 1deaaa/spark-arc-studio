"""Scriptwriter 全链路验证脚本。

覆盖 Scriptwriter 的所有 prompt 入口：
1. arc 模式 (write_script / write_script_stream)
2. novel 模式 (export_format='novel')
3. bridge 模式 (bridge_scenes / bridge_scenes_stream)
4. chat 模式 (chat / chat_stream)
5. feedback 模式 (feedback / stream_feedback)
6. _get_tool_prompt_references 双态
7. research_references (Pre-flight)
"""
import sys
sys.path.insert(0, '.')

from agents.agent_utils import load_prompt, clear_prompt_cache

errors = []
details = []

def check(label, ok):
    status = "OK" if ok else "FAIL"
    details.append(f"  {label}: {status}")
    if not ok:
        errors.append(label)

# === 1. arc 模式 ===
clear_prompt_cache()
p = load_prompt('scriptwriter', arc_example='ARC_EXAMPLE', worldview='W', roles='R',
                full_outline='FO', narrative_memory='NM', context='C', guidance='G',
                style_profile='SP', feedback='F', chr_reference='CR', length_instruction='LI')
s, u = p.get('system', ''), p.get('user', '')
check("arc/system: base.identity 替换", '执笔编剧' in s)
check("arc/system: base.creation_principles 替换", '禁止括号' in s)
check("arc/system: base.conception_spec 替换", 'conception' in s)
check("arc/system: arc_example 替换", 'ARC_EXAMPLE' in s)
check("arc/user: base.user_context 替换", '世界观背景' in u)
check("arc/system: 无未替换占位符", '{base.' not in s and '{arc_example}' not in s)
check("arc/user: 无未替换占位符", '{base.' not in u and '{worldview}' not in u)

# === 2. novel 模式 ===
clear_prompt_cache()
p2 = load_prompt('scriptwriter', 'generate_novel', worldview='W', roles='R',
                 full_outline='FO', narrative_memory='NM', context='C', guidance='G',
                 style_profile='SP', feedback='F', length_instruction='LI')
s2, u2 = p2.get('system', ''), p2.get('user', '')
check("novel/system: 小说作者身份", '小说作者' in s2)
check("novel/system: base.conception_spec 替换", 'conception' in s2)
check("novel/system: 无未替换占位符", '{base.' not in s2)
check("novel/user: worldview 替换", 'W' in u2)
check("novel/user: 无未替换占位符", '{base.' not in u2 and '{worldview}' not in u2)

# === 3. bridge 模式 ===
clear_prompt_cache()
p3 = load_prompt('scriptwriter', 'bridge', prev_scene_text='PREV', next_scene_text='NEXT',
                 pacing='fast', mood='tense', guidance='connect them')
s3, u3 = p3.get('system', ''), p3.get('user', '')
check("bridge/system: 衔接专员身份", '衔接专员' in s3)
check("bridge/user: prev_scene_text 替换", 'PREV' in u3)
check("bridge/user: next_scene_text 替换", 'NEXT' in u3)
check("bridge/user: pacing 替换", 'fast' in u3)

# === 4. chat 模式 ===
clear_prompt_cache()
p4 = load_prompt('scriptwriter')
cs, ps, s4 = p4.get('chat_system', ''), p4.get('pipeline_system', ''), p4.get('system', '')
check("chat/chat_system: base.identity 替换", '执笔编剧' in cs)
check("chat/pipeline_system: base.identity 替换", '执笔编剧' in ps)
check("chat/system: base.identity 替换", '执笔编剧' in s4)
check("chat/pipeline_system: 受众声明", '导演' in ps)
check("chat/tool_rules: 存在", bool(p4.get('tool_rules', '').strip()))

# === 5. feedback 模式 (使用顶层 system + user) ===
clear_prompt_cache()
p5 = load_prompt('scriptwriter', worldview='W', roles='R', context='C', guidance='G',
                 style_profile='SP', feedback='请只提供讨论', chr_reference='CR',
                 arc_example='ARC', length_instruction='LI')
s5, u5 = p5.get('system', ''), p5.get('user', '')
check("feedback/system: base.identity 替换", '执笔编剧' in s5)
check("feedback/system: arc_example 替换", 'ARC' in s5)
check("feedback/user: base.user_context 替换", '世界观背景' in u5)

# === 6. _get_tool_prompt_references 双态 ===
from core.request_context import set_current_export_format
from agents.agent_scriptwriter import ScriptwriterAgent

set_current_export_format('arc')
agent = ScriptwriterAgent.__new__(ScriptwriterAgent)
refs_arc = agent._get_tool_prompt_references()

set_current_export_format('novel')
refs_novel = agent._get_tool_prompt_references()

check("tool_ref[arc]: create_or_rewrite_script -> system",
      refs_arc.get('create_or_rewrite_script', [{}])[0].get('field') == 'system')
check("tool_ref[arc]: 无 prompt_key (顶层)",
      'prompt_key' not in refs_arc.get('create_or_rewrite_script', [{}])[0])
check("tool_ref[novel]: create_or_rewrite_script -> generate_novel",
      refs_novel.get('create_or_rewrite_script', [{}])[0].get('prompt_key') == 'generate_novel')
check("tool_ref[novel]: field=system",
      refs_novel.get('create_or_rewrite_script', [{}])[0].get('field') == 'system')

# === 7. research_references (Pre-flight) ===
# Pre-flight 使用硬编码 system prompt，不走 YAML，这是设计如此
details.append("  research_references: 硬编码 prompt（设计如此，非 YAML 入口）")

# === 输出 ===
print("===== Scriptwriter 全链路验证 =====")
for d in details:
    print(d)
print(f"\n错误: {len(errors)}")
for e in errors:
    print(f"  ❌ {e}")
if not errors:
    print("✅ 全部通过")
else:
    print(f"❌ {len(errors)} 个错误需要修复")

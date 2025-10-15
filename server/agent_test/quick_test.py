"""
快速测试: 使用已有风格文件进行续写
"""
import sys
import io

# 设置stdout编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from agent_style import generate_continuation

print("=" * 80)
print("快速续写测试 (使用已有风格文件)")
print("=" * 80)

# 测试场景
author_id = "author_yoru_otsuichi"
scene = """
《没有你的世界，音色皆无》

这是一个关于盲人少女和聋哑少年的故事。

她叫美咲，自小失明，却能通过声音感知世界的色彩。
他叫翔太，天生失聪，只能用眼睛记录这个无声的世界。

那个雨天，他们在图书馆第一次相遇...
"""

print(f"\n作者ID: {author_id}")
print(f"场景:\n{scene}\n")

print("-" * 80)
print("生成续写中...")
print("-" * 80)

try:
    # 生成不同类型的续写
    
    print("\n【1. 对话场景】")
    print("=" * 80)
    dialogue = generate_continuation(author_id, scene, content_type="dialogue")
    print(dialogue)
    
    print("\n\n【2. 内心独白】")
    print("=" * 80)
    monologue = generate_continuation(author_id, scene, content_type="monologue")
    print(monologue)
    
    print("\n\n【3. 旁白描写】")
    print("=" * 80)
    narrative = generate_continuation(author_id, scene, content_type="narrative")
    print(narrative)
    
    print("\n\n【4. 混合风格】")
    print("=" * 80)
    mixed = generate_continuation(author_id, scene, content_type="mixed")
    print(mixed)
    
except FileNotFoundError:
    print(f"\n✗ 未找到作者 '{author_id}' 的风格文件")
    print("请先运行 test_full_chapters.py 提取风格数据")
except Exception as e:
    print(f"\n✗ 生成失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("✓ 测试完成")
print("=" * 80)

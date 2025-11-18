import os, json
from agent_fix import repair_story_text, check_story_data

# 更自然的长剧情文本，只包含“结构/类型”层面的少量格式错误（合法 JSON，且不在文本内容上提示错误）
malformed_text = r'''
[
{
    "scene": "灯塔之下",
    "cap": "雾里有人影",
    "dia": [
      {
        "chr": 1,
        "txt": "有人在那儿挥"
      },
      {
        "id": 20002,
        "chr": 0,
        "txt": "别靠太近，先确认对方意图。"
        "opt": [
          {
            "dia": [
              {
                "id": 200021,
                "chr": 0,
                "txt": "发出警示。"
              },
              {
                "id": 200022,
                "chr": 0,
                "txt": "你要承担代价。"
              }
            ]
          }
        ]
      }
    ]
  }
]
'''

example_file = os.path.join("server", "剧本示例.story")

ok, result = repair_story_text(malformed_text, example_file=example_file, max_iters=5, debug=True)
print("修复是否成功:", ok)
if ok:
    fixed_text = result if isinstance(result, str) else str(result)
    # 写出便于人工查看
    out_path = os.path.join("server", "_tmp_fixed.story")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(fixed_text)
    print("已写出:", out_path)

    try:
        data = json.loads(fixed_text)
    except Exception as e:
        print("修复输出 JSON 解析失败:", e)
        raise SystemExit(1)

    ok2, errs2 = check_story_data(data)
    print("修复后再次校验:", "合格" if ok2 else "不合格")
    if not ok2:
        for e in errs2[:20]:
            print(" -", e)
  # 预览输出已在 fix_agent 的 debug 打印中给出原始 RAW_OUTPUT，这里不再打印预览
else:
    # 打印错误摘要
    if isinstance(result, list):
        for e in result[:30]:
            print(" -", e)
    else:
        print(result)

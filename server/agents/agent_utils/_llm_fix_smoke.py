import os
from .agent_fix import repair_arc_text, check_arc_data
from server.story.arc_parser import parse_arc

# ARC 格式的长剧情文本，包含一些格式错误（如缺少标题，或不规范的标记）
malformed_arc = r'''
# 灯塔之下
@guide 雾里有人影

[1]
有人在那儿挥手...

[-1]
别靠太近，先确认对方意图。
<choice>
<opt text="发出警示">
[0]
喂！你是谁？
</opt>
<opt text="你要承担代价">
[0]
看来你选择了死亡。
</opt>
</choice>
'''

ok, result = repair_arc_text(malformed_arc, max_iters=3, debug=True)
print("Fix succeeded:", ok)
if ok:
    fixed_text = result if isinstance(result, str) else str(result)
    # 写出便于人工查看
    out_path = os.path.join("server", "_tmp_fixed.arc")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(fixed_text)
    print("Written to:", out_path)

    try:
        data = parse_arc(fixed_text)
    except Exception as e:
        print("Fix output ARC parse failed:", e)
        raise SystemExit(1)

    ok2, errs2 = check_arc_data(data)
    print("Post-fix re-check:", "Pass" if ok2 else "Fail")
    if not ok2:
        for e in errs2[:20]:
            print(" -", e)
else:
    # 打印错误摘要
    if isinstance(result, list):
        for e in result[:30]:
            print(" -", e)
    else:
        print(result)

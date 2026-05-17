using System;
using System.Collections.Generic;
using System.Drawing;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using DialogSystem.Services;
using Newtonsoft.Json.Linq;

namespace DialogSystem
{
    class DialogGroup
    {
        public JArray Array;
        public int NextIndex;
        public DialogGroup(JArray array)
        {
            Array = array;
            NextIndex = 0; // 0 才是有效的第一个
        }
    }

    static class Dialog
    {
        public static JToken DialogScene; // 当前场景
        static readonly Stack<DialogGroup> DialogArray = new Stack<DialogGroup>();
        public static JObject CurrentObj; // 目前遍历到的对话对象
        public static int Choice = 0; // 注意 从1开始
        public static int CurrentGroupObjIndex = 0; // 目前遍历到的组内对话对象
        public static int scene_index = 0; // 当前场景下主线对话索引
        static StoryRepository _repository;

        static bool waitForChoice = false; // 是否处于等待选项状态
        public static bool EndDialog = false; // 下一次点击直接关闭对话
        static string NextDialog = null; // 指定 next 所指向的下一个对话场景，为 null 表示不跳转
        static readonly List<ChoiceBtn> branch_btns = new List<ChoiceBtn>(); // 选项按钮
        public static bool DialogEnabled = true; // 是否启用对话

        public static bool AllowSkip = true; // 是否允许跳过对话
        public static bool IsTypingTxt = false; // 是否正在打字
        public static int TypingSpeed = 40; // 打字间隔毫秒
        static CancellationTokenSource cancel; // 用于取消当前的打印任务

        public static void ConfigureRepository(StoryRepository repository)
        {
            _repository = repository;
        }

        public static JArray CrtArray
        {
            get { return DialogArray.Count > 0 ? DialogArray.Peek().Array : null; }
            set { if (DialogArray.Count > 0) DialogArray.Peek().Array = value; }
        }

        public static int CrtIndex
        {
            get { return DialogArray.Count > 0 ? DialogArray.Peek().NextIndex : 0; }
            set { if (DialogArray.Count > 0) DialogArray.Peek().NextIndex = value; }
        }

        public static void SceneInit(string scene)
        {
            if (_repository == null)
            {
                Method.Error("对话系统尚未注入剧情数据仓库");
                return;
            }

            DialogScene = _repository.GetSceneObj(scene); // 根（场景）键值对的值为数组
            if (DialogScene == null)
            {
                Method.Error($"Scene '{scene}' not found in JsonSource!");
                return;
            }

            CurrentGroupObjIndex = 0;
            NextDialog = null;
            waitForChoice = false;
            Program.UI.cap.Text = DialogScene["guide"]?.ToString() ?? string.Empty;

            // 场景引言：在场景标题下方显示的简短介绍文本
            var introText = DialogScene["intro"]?.ToString();
            if (!string.IsNullOrWhiteSpace(introText))
                Method.Inf($"[Intro] {introText}");

            // TODO: effects — 场景播放完成后写回到 StoryStateStore 的效果列表，待接入状态系统
            // var effects = DialogScene["effects"];

            // TODO: trigger_event — 外部系统事件回调键，待接入游戏事件系统
            // var triggerEvent = DialogScene["trigger_event"]?.ToString();

            // TODO: priority — 同一触发点命中多个场景时的优先级，待接入场景调度器
            // var priority = DialogScene["priority"]?.Value<int>() ?? 0;

            // TODO: once_key — 一次性剧情标记键，播放完成后自动写入已播状态，待接入状态系统
            // var onceKey = DialogScene["once_key"]?.ToString();

            DialogArray.Clear();

            if (DialogScene["dia"] == null)
            {
                Method.Error($"Scene '{scene}' does not contain 'dia' array!");
                return;
            }

            DialogArray.Push(new DialogGroup((JArray)DialogScene["dia"]));

            if (CrtArray == null || CrtArray.Count == 0)
            {
                Method.Error($"Dialog array for scene '{scene}' is empty!");
                return;
            }

            CurrentObj = (JObject)CrtArray[0];
            CrtIndex = 0;
        }

        static void ChoiceBtn_Click(object sender, EventArgs e)
        {
            ChoiceBtn clicked_btn = (ChoiceBtn)sender;
            Choice = clicked_btn.Choice;

            if (CurrentObj == null || !CurrentObj.ContainsKey("opt"))
            {
                Method.Error("Invalid choice button click - CurrentObj has no options!");
                return;
            }

            JArray options = (JArray)CurrentObj["opt"];
            if (Choice < 1 || Choice > options.Count)
            {
                Method.Error($"Invalid choice index: {Choice}. Valid range: 1-{options.Count}");
                return;
            }

            JObject selectedOption = (JObject)options[Choice - 1];
            if (!selectedOption.ContainsKey("dia"))
            {
                Method.Error("Selected option does not contain 'dia' key!");
                return;
            }

            JArray diaArray = (JArray)selectedOption["dia"];
            DialogArray.Push(new DialogGroup(diaArray));

            if (DialogArray.Count > 0 && CrtArray != null && CrtArray.Count > 0)
            {
                CurrentObj = (JObject)CrtArray[0];
                CrtIndex = 0;
            }
            else
            {
                Method.Error("Failed to get valid dialog array after choice!");
                return;
            }

            foreach (var btn in branch_btns)
                btn.Dispose();
            branch_btns.Clear();
            DisplayOne(CurrentObj, Program.UI);
        }

        public static async Task TypingTxtAsync(string txt, Label label)
        {
            label.Text = string.Empty;
            IsTypingTxt = true;

            cancel?.Cancel();
            var currentCancelTokenSource = new CancellationTokenSource();
            cancel = currentCancelTokenSource;
            var token = currentCancelTokenSource.Token;

            System.Text.StringBuilder sb = new System.Text.StringBuilder();
            for (int i = 0; i < txt.Length; i++)
            {
                if (token.IsCancellationRequested)
                {
                    break;
                }

                sb.Append(txt[i]);
                label.Text = sb.ToString();
                try
                {
                    await Task.Delay(TypingSpeed, token);
                }
                catch (TaskCanceledException)
                {
                    break;
                }
            }

            IsTypingTxt = false;
        }

        public static void DisplayOne(JObject crt_obj, MainUI ui)
        {
            #region 处理跳转和初始化
            if (EndDialog)
            {
                End(ui);
                EndDialog = false;
                return;
            }
            if (NextDialog != null)
            {
                SceneInit(NextDialog);
                DisplayOne(CurrentObj, Program.UI);
                return;
            }
            if (DialogArray.Count == 0)
            {
                Method.Error("DialogArray is empty! Please call SceneInit first.");
                return;
            }
            waitForChoice = false;
            DialogEnabled = true;
            #endregion

            foreach (JProperty key in crt_obj.Properties())
            {
                switch (key.Name)
                {
                    case "chr":
                        if (!Map.ChrMap.TryGetValue((int)key.Value, out var name))
                            name = key.Value.ToString();
                        ui.spk.Text = name;
                        break;
                    case "txt":
                        if (cancel != null && cancel.Token.CanBeCanceled)
                            cancel.Cancel();

                        cancel = new CancellationTokenSource();
                        _ = TypingTxtAsync(key.Value.ToString(), ui.txt);
                        break;
                    case "act":
                        foreach (JProperty acts in key.Value)
                        {
                            try
                            {
                                string fun = acts.Name;
                                string[] args;
                                if (acts.Value.Type == JTokenType.Array)
                                {
                                    args = acts.Value.ToObject<string[]>();
                                }
                                else
                                {
                                    args = acts.Value.ToString().Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                                }

                                if (args.Length == 0)
                                {
                                    if (Map.ActMap.ContainsKey(fun))
                                        Map.ActMap[fun]();
                                    else
                                        Method.Error($"[{acts.Name}]未绑定到函数");
                                }
                                else if (Map.ActArgMap.ContainsKey(fun))
                                {
                                    Map.ActArgMap[fun](args);
                                }
                                else if (Map.ActMap.ContainsKey(fun))
                                {
                                    Map.ActMap[fun]();
                                }
                                else
                                {
                                    Method.Error($"[{acts.Name}]未绑定到函数");
                                }
                            }
                            catch (Exception ex)
                            {
                                Method.Error($"[{acts.Name}]执行出错: {ex.Message}");
                            }
                        }
                        break;
                    case "opt":
                        DialogEnabled = false;
                        waitForChoice = true;
                        int i = 1;
                        foreach (JObject option in key.Value)
                        {
                            ChoiceBtn btn = new ChoiceBtn();
                            branch_btns.Add(btn);
                            btn.Text = option["optn"].ToString();
                            btn.Choice = i;

                            btn.Size = new Size(200, 50);
                            btn.Location = new Point(ui.Width - 200, btn.Size.Height * i);
                            btn.Click += ChoiceBtn_Click;
                            ui.Controls.Add(btn);
                            i++;
                        }
                        break;
                    case "next":
                        NextDialog = key.Value.ToString();
                        break;
                    // thought: 辅助AI决策的字段，运行时不需要处理
                    case "thought":
                        break;
                }
            }

            if (DialogArray.Count == 0)
            {
                Method.Error("DialogArray became empty during processing!");
                return;
            }

            if (CrtIndex < CrtArray.Count)
                CrtIndex++;
            if (waitForChoice)
                return;
            if (NextDialog != null)
            {
                SceneInit(NextDialog);
                return;
            }

            if (DialogArray.Count == 0)
            {
                Method.Error("DialogArray is empty after NextDialog processing!");
                return;
            }

            if (CrtArray != null && CrtArray.Count - CrtIndex == 0)
            {
                while (DialogArray.Count > 0 && CrtArray != null && CrtArray.Count - CrtIndex == 0)
                {
                    DialogArray.Pop();
                    if (DialogArray.Count == 0)
                    {
                        if (_repository?.JsonSource == null || scene_index >= _repository.JsonSource.Count - 1)
                        {
                            EndDialog = true;
                            return;
                        }
                        SceneInit(_repository.JsonSource[++scene_index]["scene"].ToString());
                        return;
                    }
                }
                if (DialogArray.Count > 0 && CrtArray != null && CrtIndex < CrtArray.Count)
                {
                    CurrentObj = (JObject)CrtArray[CrtIndex];
                }
            }
            else if (DialogArray.Count > 0 && CrtArray != null && CrtArray.Count - CrtIndex > 0)
            {
                CurrentObj = (JObject)CrtArray[CrtIndex];
            }
        }

        public static void ResetDialog()
        {
            Choice = 0;
            CurrentGroupObjIndex = 0;
            scene_index = 0;
            DialogArray.Clear();
            CurrentObj = null;
            waitForChoice = false;
            EndDialog = false;
            NextDialog = null;

            foreach (var btn in branch_btns)
            {
                btn.Dispose();
            }
            branch_btns.Clear();

            cancel?.Cancel();
            cancel = null;
            IsTypingTxt = false;
            DialogEnabled = true;
        }

        public static void End(MainUI ui)
        {
            ui.Close();
        }

        class ChoiceBtn : Button
        {
            public int Choice = 0;
        }
    }
}

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using System.Threading;
using Newtonsoft.Json.Linq;
using System.Threading.Tasks;

namespace DialogSystem
{
    public partial class MainUI : Form
    {
        // 对话脚本结构中 之所以不用键名存储实际文本 是因为键名无法被修改
        public MainUI()
        {
            CheckForIllegalCrossThreadCalls = false;
            InitializeComponent();
            Map.ActArgMap["trans"] = Trans; // 使用索引器确保覆盖或添加
        }

        public static void Trans(string[] xy)
        {
            if (xy == null || xy.Length < 2)
            {
                Method.Error("trans 参数不足");
                return;
            }
            Method.Inf("正在播放" + xy[0] + "，" + xy[1]);
        }

        private void txt_Click(object sender, EventArgs e)
        {
            if (!Dialog.DialogEnabled)
                return;
            if (Dialog.IsTypingTxt && !Dialog.AllowSkip)
                return;
            Dialog.DisplayOne(Dialog.CurrentObj, this);
        }

        private void MainUI_Load(object sender, EventArgs e)
        {
            if (string.IsNullOrEmpty(Manager.DataFilePath) || !System.IO.File.Exists(Manager.DataFilePath))
            {
                Method.Error("故事文件不存在，请先在编辑器中保存或选择有效路径。");
                return;
            }
            Manager.JsonSource = JArray.Parse(System.IO.File.ReadAllText(Manager.DataFilePath));
            if (Manager.JsonSource == null || Manager.JsonSource.Count == 0)
            {
                Method.Error("故事数据为空");
                return;
            }
            Dialog.ResetDialog(); // 重置对话状态
            Dialog.SceneInit(Manager.JsonSource[0]["scene"].ToString());//获取第一个场景名
            Dialog.DisplayOne(Dialog.CurrentObj, this);
        }
    }

    class DialogGroup
    {
        public JArray Array;
        public int NextIndex;
        public DialogGroup(JArray _array)
        {
            Array = _array;
            NextIndex = 0; // 0才是有效的第一个
        }
    }

    static class Dialog
    {
        public static JToken DialogScene;//当前场景
        static Stack<DialogGroup> DialogArray = new Stack<DialogGroup>();
        public static JObject CurrentObj; // 目前遍历到的对话对象
        public static int Choice = 0; // 注意 从1开始!!!
        public static int CurrentGroupObjIndex = 0; // 目前遍历到的组内对话对象
        public static int scene_index = 0;//当前场景下主线对话索引

        static bool waitForChoice = false;//是否处于等待选项状态
        public static bool EndDialog = false; // 下一次点击直接关闭对话
        static string NextDialog = null; // 指定next所指向的下一个对话场景 为null表示不跳转
        static List<ChoiceBtn> branch_btns = new List<ChoiceBtn>();//选项按钮
        public static bool DialogEnabled = true;//是否启用对话

        public static bool AllowSkip = true;//是否允许跳过对话
        public static bool IsTypingTxt = false;//是否正在打字
        public static int TypingSpeed = 40;//打字间隔毫秒
        static CancellationTokenSource cancel; // 用于取消当前的打印任务

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

        public static void SceneInit(string _scene)
        {
            // ??= 如果为null才赋值 防止重复赋值
            DialogScene = Manager.GetSceneObj(_scene); // 根（场景）键值对的值为数组  Token代表任意数据节点 Prop代表键值对 Object代表{xxx}
            
            if (DialogScene == null)
            {
                Method.Error($"Scene '{_scene}' not found in JsonSource!");
                return;
            }

            CurrentGroupObjIndex = 0;
            NextDialog = null;
            waitForChoice = false;
            Program.UI.cap.Text = DialogScene["cap"]?.ToString() ?? "";
            DialogArray.Clear();
            
            if (DialogScene["dia"] == null)
            {
                Method.Error($"Scene '{_scene}' does not contain 'dia' array!");
                return;
            }

            DialogArray.Push(new DialogGroup((JArray)DialogScene["dia"]));

            // 确保数组有内容
            if (CrtArray == null || CrtArray.Count == 0)
            {
                Method.Error($"Dialog array for scene '{_scene}' is empty!");
                return;
            }

            CurrentObj = (JObject)CrtArray[0];
            CrtIndex = 0; // 确保索引从0开始
        }

        private static void ChoiceBtn_Click(object sender, EventArgs e) // 选项点击 也相当于点击了一次继续
        {
            ChoiceBtn clicked_btn = (ChoiceBtn)sender;
            Choice = clicked_btn.Choice;

            // 直接从当前对象获取选项
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
            DialogArray.Push(new DialogGroup(diaArray)); // 根据选项定位新的对话组
            
            // 确保栈不为空再获取当前对象
            if (DialogArray.Count > 0 && CrtArray != null && CrtArray.Count > 0)
            {
                CurrentObj = (JObject)CrtArray[0]; // 进入选项内部对话
                CrtIndex = 0;
            }
            else
            {
                Method.Error("Failed to get valid dialog array after choice!");
                return;
            }

            foreach (var i in branch_btns)
                i.Dispose(); // 关闭选项
            branch_btns.Clear();
            DisplayOne(CurrentObj, Program.UI);
        }

        public static async Task TypingTxtAsync(string txt, Label label)//异步打字
        {
            label.Text = "";
            IsTypingTxt = true;

            // 如果存在正在进行的打印任务，取消它
            cancel?.Cancel();
            var currentCancelTokenSource = new CancellationTokenSource();//创建新的取消令牌
            cancel = currentCancelTokenSource; // 将新的取消令牌源赋给静态字段
            var token = currentCancelTokenSource.Token;

            System.Text.StringBuilder sb = new System.Text.StringBuilder();
            for (int i = 0; i < txt.Length; i++)
            {
                if (token.IsCancellationRequested) // 如果任务被取消则退出
                {
                    break;
                }

                sb.Append(txt[i]);
                label.Text = sb.ToString();
                try
                {
                    await Task.Delay(TypingSpeed, token); // 异步延时，并传递取消令牌
                }
                catch (TaskCanceledException)
                {
                    break;
                }
            }

            IsTypingTxt = false;
        }

        public static void DisplayOne(JObject crt_obj, MainUI ui) // 传入一个对话对象
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
            // 添加栈空检查
            if (DialogArray.Count == 0)
            {
                Method.Error("DialogArray is empty! Please call SceneInit first.");
                return;
            }
            waitForChoice = false;
            DialogEnabled = true;
            #endregion

            foreach (JProperty key in crt_obj.Properties()) // 解析一个dia下所有参数
            {
                switch (key.Name)
                {
                    case "chr":
                        string name;
                        int chrId = (int)key.Value;
                        if (!Map.ChrMap.TryGetValue(chrId, out name)) name = chrId.ToString();
                        ui.spk.Text = name;
                        break;
                    case "txt":
                        if (cancel != null && cancel.Token.CanBeCanceled)
                            cancel.Cancel(); // 取消之前的打印任务

                        cancel = new CancellationTokenSource(); // 创建新的取消令牌
                        _ = TypingTxtAsync(key.Value.ToString(), ui.txt); // 不等待异步任务
                        break;
                    case "act":
                        foreach (JProperty acts in key.Value)
                        {
                            try
                            {
                                string fun = acts.Name.ToString();
                                string[] args = acts.Value.ToString().Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                                if (args.Length == 0)
                                    Map.ActMap[fun]();
                                else if (Map.ActArgMap.ContainsKey(fun))
                                    Map.ActArgMap[fun](args);
                                else if (Map.ActMap.ContainsKey(fun))
                                    Map.ActMap[fun]();
                                else
                                    Method.Error($"[{acts.Name}]未绑定到函数");
                            }
                            catch
                            {
                                Method.Error($"[{acts.Name}]未绑定到函数");
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

                            #region 界面相关
                            btn.Size = new Size(200, 50);
                            btn.Location = new Point(ui.Width - 200, btn.Size.Height * i);
                            btn.Click += ChoiceBtn_Click;
                            ui.Controls.Add(btn);
                            #endregion
                            i++;
                        }
                        break;
                    case "next":
                        NextDialog = key.Value.ToString();
                        break;
                }
            }

            // 解析任务结束 已经显示在屏幕上 开始定位下一次解析位置 所有current皆为下次待解析对象
            // 添加栈空检查
            if (DialogArray.Count == 0)
            {
                Method.Error("DialogArray became empty during processing!");
                return;
            }
            
            if (CrtIndex < CrtArray.Count)
                CrtIndex++;//最高的优先级 优先解析下一个对话
            if (waitForChoice)
                return;//若处于等待选项时 直接返回继续等待
            if (NextDialog != null)
            {
                SceneInit(NextDialog);
                return;
            }

            // 再次检查栈状态
            if (DialogArray.Count == 0)
            {
                Method.Error("DialogArray is empty after NextDialog processing!");
                return;
            }

            if (CrtArray != null && CrtArray.Count - CrtIndex == 0) // 本层已全部解析完毕 退出本层
            {
                while (DialogArray.Count > 0 && CrtArray != null && CrtArray.Count - CrtIndex == 0)
                {
                    DialogArray.Pop();
                    if (DialogArray.Count == 0) // 场景所有对话结束
                    {
                        if (scene_index >= Manager.JsonSource.Count - 1)
                        {
                            EndDialog = true;
                            return;
                        }
                        SceneInit(Manager.JsonSource[++scene_index]["scene"].ToString());
                        // 下次点击 在事件开头直接退出
                        return;
                    }
                }
                // 确保栈不为空且有有效数据
                if (DialogArray.Count > 0 && CrtArray != null && CrtIndex < CrtArray.Count)
                {
                    CurrentObj = (JObject)CrtArray[CrtIndex]; // 切换到外层
                }
            }
            else if (DialogArray.Count > 0 && CrtArray != null && CrtArray.Count - CrtIndex > 0)
            {
                CurrentObj = (JObject)CrtArray[CrtIndex];
            }
        }

        public static void ResetDialog()
        {
            // 重置所有对话状态
            Choice = 0;
            CurrentGroupObjIndex = 0;
            scene_index = 0;
            DialogArray.Clear();
            CurrentObj = null;
            waitForChoice = false;
            EndDialog = false;
            NextDialog = null;
            
            // 清理选项按钮
            foreach (var btn in branch_btns)
            {
                btn.Dispose();
            }
            branch_btns.Clear();
            
            // 取消正在进行的打字效果
            cancel?.Cancel();
            cancel = null;
            IsTypingTxt = false;
                  // 重置对话启用状态
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

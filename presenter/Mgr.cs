using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Drawing;
using Newtonsoft.Json.Linq;
using System.Xml.Linq;
using DialogSystem;
using System.IO;

namespace DialogSystem
{    public class Manager
    {
        //脚本位置
        public static string DataFilePath = "../../测试故事.story";
        public static JArray JsonSource;
        public static Stack<JArray> History=new Stack<JArray>();
        public static JObject GetSceneObj(string scene)
        {
            if (JsonSource == null || string.IsNullOrEmpty(scene))
                return null;
            foreach (var obj in JsonSource)
            {
                if (obj["scene"] != null && obj["scene"].ToString() == scene)
                    return obj as JObject;
            }
            return null;
        }
    }
    public enum NodeType
    {
        None,
        DlgWithOpt,
        DlgWithAct,
        OptItem,
        ActItem,
        Dialog,
        Scene,
        Next,
    }
    public static class ThemeColor
    {
        public static Color Option = Color.LimeGreen;
        public static Color Action = Color.Orange;
        public static Color Dialog = Color.White;
        public static Color Branch = Color.SkyBlue;
        public static Color Next = Color.BlueViolet;
        public static Color Scene = Color.DarkTurquoise;
    }
    public class RichNode : TreeNode
    {
        public int id = -1;
        public string scene = null;
        //以上是每个节点都有的属性
        public int chr = -1;
        public string txt = null;
        public string next = null;
        //dlg节点的属性
        public string opt = null;
        //opt名字节点的属性
        public string act_fun = null;
        public string scene_cap=null;
        public string scene_pgrs = null;
        public string _act_args = null;
        public NodeType _NodeType=NodeType.None;
        public NodeType NodeType
        {
            get { return _NodeType; }
            set
            {
                _NodeType = value;
                switch (value)
                {
                    case NodeType.DlgWithOpt:
                        BackColor = ThemeColor.Option;
                        break;
                    case NodeType.DlgWithAct:
                        BackColor = ThemeColor.Action;
                        break;
                    case NodeType.OptItem:
                        ForeColor = ThemeColor.Option;
                        break;
                    case NodeType.ActItem:
                        ForeColor = ThemeColor.Action;
                        break;
                    case NodeType.Dialog:
                        BackColor= ThemeColor.Dialog;
                        opt = null;
                        break;
                    case NodeType.Scene:
                        BackColor = ThemeColor.Scene;
                        break;
                    case NodeType.Next:
                        ForeColor = ThemeColor.Next;
                        break;
                    default:
                        break;
                }
            }
        }
        public RichNode(string t)
        {
            Text = t;
        }
    }
    public class Map//映射表
    {
        public static Dictionary<string, Action> ActMap = new Dictionary<string, Action>
        {
            #region 行为映射表
            // 绑定全局指令和函数 其余的可以动态添加
            { "exit", Method.Exit }
            #endregion 行为映射表
        };
        public static Dictionary<string, Action<string[]>> ActArgMap = new Dictionary<string, Action<string[]>>
        {
            #region 行为映射表
            // 绑定所有指令和函数
            { "bgm", Method.Music }
            #endregion 行为映射表
        };


        public static Dictionary<int, string> ChrMap = new Dictionary<int, string>
        {
            #region 角色映射表
            { 0, " " },
            { 1, "我" },
            { 2, "初音" },
            { 3, "心声" }
            #endregion 角色映射表
        };
    }
    public static class Method //一些杂项 无需迁移到Unity
    {
        public static string GetRandomString(int length)
        {
            Random random = new Random();
            StringBuilder stringBuilder = new StringBuilder(length);
            for (int i = 0; i < length; i++)
            {
                char asciiChar = (char)(random.Next(32, 127)); // 32 到 126 是可打印的 ASCII 范围
                stringBuilder.Append(asciiChar);
            }
            return stringBuilder.ToString();
        }
        public static void Error(object e)
        {
            MessageBox.Show(e.ToString(), "o(TヘTo)", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        public static void Inf(object e)
        {
            MessageBox.Show(e.ToString(), "o(=•ェ•=)m", MessageBoxButtons.OK,MessageBoxIcon.Information );
        }
        public static bool Warn(object e)
        {
            if (MessageBox.Show(e.ToString(), "⚠️", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes)
                return true;
            return false;
        }
        public static DialogResult Ask(object e)
        {
            return MessageBox.Show(e.ToString(), "⚠️", MessageBoxButtons.YesNoCancel, MessageBoxIcon.Warning);
        }
        public static void Music(string[] bgm)
        {
            Method.Inf("正在播放" + bgm[0]);
        }

        public static void Exit()
        {
            Application.Exit();
        }
        public static void RecordBranch(string brc)
        {
            
        }
    }
}

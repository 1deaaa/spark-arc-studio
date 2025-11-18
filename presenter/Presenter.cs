using System;
using System.Windows.Forms;
using Newtonsoft.Json.Linq;
using DialogSystem.Services;

namespace DialogSystem
{
    public partial class MainUI : Form
    {
        private readonly StoryRepository _repository = new StoryRepository();

        // 对话脚本结构中 之所以不用键名存储实际文本 是因为键名无法被修改
        public MainUI()
        {
            CheckForIllegalCrossThreadCalls = false;
            InitializeComponent();
            Map.ActArgMap["trans"] = Trans; // 使用索引器确保覆盖或添加
            Dialog.ConfigureRepository(_repository);
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
            if (!_repository.LoadDefaultSource(out var error))
            {
                Method.Error(error ?? "无法加载默认故事，请手动选择 .story 文件");
                UpdateSourceLabel();
                return;
            }

            TryStartPlayback();
        }

        private void btnLoadStory_Click(object sender, EventArgs e)
        {
            using (var dialog = new OpenFileDialog())
            {
                dialog.Filter = "Story 文件 (*.story)|*.story|JSON 文件 (*.json)|*.json|所有文件 (*.*)|*.*";
                dialog.Title = "选择 Story 文件";
                if (dialog.ShowDialog() == DialogResult.OK)
                {
                    if (!_repository.LoadFromStoryFile(dialog.FileName, out var error))
                    {
                        Method.Error(error ?? "加载 Story 文件失败");
                        return;
                    }

                    TryStartPlayback();
                }
            }
        }

        private bool TryStartPlayback()
        {
            if (_repository.JsonSource == null || _repository.JsonSource.Count == 0)
            {
                Method.Error("故事数据为空");
                return false;
            }

            var firstSceneToken = _repository.JsonSource[0]?["scene"];
            if (firstSceneToken == null || string.IsNullOrWhiteSpace(firstSceneToken.ToString()))
            {
                Method.Error("故事缺少可用的首场景");
                return false;
            }

            Dialog.ResetDialog();
            Dialog.SceneInit(firstSceneToken.ToString());
            UpdateSourceLabel();
            Dialog.DisplayOne(Dialog.CurrentObj, this);
            return true;
        }

        private void UpdateSourceLabel()
        {
            var source = _repository.CurrentSourceLabel;
            label1.Text = string.IsNullOrWhiteSpace(source) ? "来源: 未加载" : $"来源: {source}";
        }
    }

}

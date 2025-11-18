namespace DialogSystem
{
    partial class MainUI
    {
        /// <summary>
        /// 必需的设计器变量。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// 清理所有正在使用的资源。
        /// </summary>
        /// <param name="disposing">如果应释放托管资源，为 true；否则为 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows 窗体设计器生成的代码

        /// <summary>
        /// 设计器支持所需的方法 - 不要修改
        /// 使用代码编辑器修改此方法的内容。
        /// </summary>
        private void InitializeComponent()
        {
            this.txt = new System.Windows.Forms.Label();
            this.spk = new System.Windows.Forms.Label();
            this.label1 = new System.Windows.Forms.Label();
            this.cap = new System.Windows.Forms.Label();
            this.btnLoadStory = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // txt
            // 
            this.txt.BackColor = System.Drawing.Color.PaleTurquoise;
            this.txt.Cursor = System.Windows.Forms.Cursors.Default;
            this.txt.Font = new System.Drawing.Font("微软雅黑 Light", 15F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.txt.ForeColor = System.Drawing.SystemColors.ControlText;
            this.txt.Location = new System.Drawing.Point(-2, 374);
            this.txt.Margin = new System.Windows.Forms.Padding(2, 0, 2, 0);
            this.txt.Name = "txt";
            this.txt.Size = new System.Drawing.Size(837, 122);
            this.txt.TabIndex = 0;
            this.txt.Text = "对话框";
            this.txt.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            this.txt.Click += new System.EventHandler(this.txt_Click);
            // 
            // spk
            // 
            this.spk.BackColor = System.Drawing.Color.PaleTurquoise;
            this.spk.Font = new System.Drawing.Font("微软雅黑 Light", 15F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.spk.ForeColor = System.Drawing.Color.SeaGreen;
            this.spk.Location = new System.Drawing.Point(358, 374);
            this.spk.Margin = new System.Windows.Forms.Padding(2, 0, 2, 0);
            this.spk.Name = "spk";
            this.spk.Size = new System.Drawing.Size(116, 26);
            this.spk.TabIndex = 1;
            this.spk.Text = "角色";
            this.spk.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // label1
            // 
            this.label1.BackColor = System.Drawing.Color.Transparent;
            this.label1.Font = new System.Drawing.Font("微软雅黑 Light", 20F);
            this.label1.ForeColor = System.Drawing.Color.Black;
            this.label1.Location = new System.Drawing.Point(8, 7);
            this.label1.Margin = new System.Windows.Forms.Padding(2, 0, 2, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(180, 51);
            this.label1.TabIndex = 2;
            this.label1.Text = "来源: 未加载";
            this.label1.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // cap
            // 
            this.cap.BackColor = System.Drawing.Color.Transparent;
            this.cap.Font = new System.Drawing.Font("微软雅黑", 10.5F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.cap.ForeColor = System.Drawing.SystemColors.ActiveCaptionText;
            this.cap.Location = new System.Drawing.Point(-2, 200);
            this.cap.Margin = new System.Windows.Forms.Padding(2, 0, 2, 0);
            this.cap.Name = "cap";
            this.cap.Size = new System.Drawing.Size(382, 31);
            this.cap.TabIndex = 3;
            this.cap.Text = "任务提示";
            this.cap.TextAlign = System.Drawing.ContentAlignment.MiddleLeft;
            // 
            // btnLoadStory
            // 
            this.btnLoadStory.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.btnLoadStory.Location = new System.Drawing.Point(663, 13);
            this.btnLoadStory.Name = "btnLoadStory";
            this.btnLoadStory.Size = new System.Drawing.Size(160, 34);
            this.btnLoadStory.TabIndex = 4;
            this.btnLoadStory.Text = "打开 .story 文件";
            this.btnLoadStory.UseVisualStyleBackColor = true;
            this.btnLoadStory.Click += new System.EventHandler(this.btnLoadStory_Click);
            // 
            // MainUI
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 12F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.BackColor = System.Drawing.Color.White;
            this.ClientSize = new System.Drawing.Size(835, 495);
            this.Controls.Add(this.btnLoadStory);
            this.Controls.Add(this.cap);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.spk);
            this.Controls.Add(this.txt);
            this.FormBorderStyle = System.Windows.Forms.FormBorderStyle.Fixed3D;
            this.Location = new System.Drawing.Point(2000, 2000);
            this.Margin = new System.Windows.Forms.Padding(2, 1, 2, 1);
            this.MaximizeBox = false;
            this.Name = "MainUI";
            this.Text = "MainUI";
            this.TopMost = true;
            this.Load += new System.EventHandler(this.MainUI_Load);
            this.ResumeLayout(false);

        }

        #endregion
        public System.Windows.Forms.Label txt;
        public System.Windows.Forms.Label spk;
        public System.Windows.Forms.Label label1;
        public System.Windows.Forms.Label cap;
        private System.Windows.Forms.Button btnLoadStory;
    }
}


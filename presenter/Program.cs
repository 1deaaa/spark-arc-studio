using System;
using System.Windows.Forms;

namespace DialogSystem
{
    internal static class Program
    {
        public static MainUI UI;
        /// <summary>
        /// 应用程序的主入口点。
        /// </summary>
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            try
            {
                UI=new MainUI();
            }
            catch (Exception ex)
            {
                MessageBox.Show("初始化主界面失败: " + ex.Message, "Error");
                return;
            }
            Application.Run(UI);
        }
    }
}

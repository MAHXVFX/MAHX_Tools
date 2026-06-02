# MA Automation

**自动化批处理执行工具**

## 功能
- **按钮点击**：执行指定 Houdini 节点上的按钮参数
- **Flipbook (拍屏)**：在场景视图中执行拍屏并可选输出到磁盘
- **HomeAssistant Webhook**：发送 Webhook 请求到 HomeAssistant

## 使用说明
1. 在 MA ShelfTools Pro 面板中点击 "MA Automation" 缩略图
2. 在弹出的窗口中添加任务（+ 按钮）
3. 每个任务选择类型后填写对应参数
4. 点击 Start 开始执行任务序列

## 提示
- 任务按顺序执行，失败的任务会跳过并继续
- 支持 Auto Fill 功能：选中节点后点击 Auto Fill 自动填充 execute 按钮
- 任务列表自动保存到当前工程目录（$HIP/MAJson/MA_Automation.json）

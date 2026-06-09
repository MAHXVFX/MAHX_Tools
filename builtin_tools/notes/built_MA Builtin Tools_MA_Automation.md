# MA Automation

**自动化批处理执行工具**

## 功能
- **按钮点击**：执行指定 Houdini 节点上的按钮参数
- **Flipbook (拍屏)**：在场景视图中执行拍屏，支持用户自定义帧范围和输出路径
- **HomeAssistant Webhook**：发送 Webhook 请求到 HomeAssistant

## 使用说明
1. 在 MA ShelfTools Pro 面板中点击 "MA Automation" 缩略图
2. 在弹出的窗口中添加任务（+ 按钮）
3. 每个任务选择类型后填写对应参数
4. 点击 执行 开始执行任务序列

## 任务类型

### 按钮点击
- 输入 Houdini 参数路径（如 `/obj/geo1/execute`）
- 支持从 Houdini 参数面板直接拖入

### Flipbook
- **帧范围**：输入起始帧和结束帧（支持 `$RFSTART` / `$RFEND` 等表达式）
- **输出路径**：设置输出文件路径（支持 `$HIP` / `$HIPNAME` / `$F4` 等表达式）
- **保存到磁盘**：勾选后输出到指定路径，取消勾选仅预览不保存
- 输出路径旁有文件夹按钮，可快速打开输出目录

### HomeAssistant Webhook
- 输入 Webhook URL

### 提示
> - 任务按顺序执行，失败的任务会跳过并继续
> - 支持自动填充功能：选中节点后点击 自动填充 自动填充 execute 按钮
> - 任务列表自动保存到当前工程目录（$HIP/MA Automation/json/MA_Automation.json）
> - 支持多配置文件：可在配置下拉框中选择或键入不同配置名

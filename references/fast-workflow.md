# 固定工作流与计时

使用已安装的本技能 Python 环境执行以下命令；路径均相对本技能目录。首次安装和模型缓存方式见 transcription.md。

默认 `<交付目录>` 为 `~/Documents/面试录音分析/YYYY-MM-DD-面试名称/`；用户显式指定输出目录时使用指定位置，同名目录追加序号。先把原始录音按原文件名与扩展名复制到该目录，保留源文件；最终交付原始录音、`转写稿.txt` 和 `面试复盘报告.html`。工作目录存放分析、计时和截图，不混入最终交付子目录。

## 处理顺序

1. 用 `scripts/transcribe.py` 一次全量转写，传 `--timestamps --metrics-output <工作目录>/转写计时.json --output <交付目录>/转写稿`。只在歧义影响评价时局部重转，通常一轮，保留完整上下文与初始结果。
2. 执行：

```bash
python scripts/prepare_analysis.py --transcript <交付目录>/转写稿.txt \
  --work-dir <工作目录> --title <面试名称> --audio <录音文件名> --date YYYY-MM-DD
```

阅读全文 `阅读稿.txt`，直接填写生成的 `分析.json`，结构遵循 analysis-schema.md。空草稿不包含任何自动推断的问答或评价，必须由 Codex 完成。无需重新打印全部 JSON、转换旧报告或临时编写内容生成脚本。片段编号对应原文行号，时间与原话可直接引用。重复运行会保留已有分析；输入或元数据变化时要求使用新工作目录，避免证据失配。

3. 一次验证并渲染：

```bash
python scripts/render_review.py --transcript <交付目录>/转写稿.txt \
  --analysis <工作目录>/分析.json --output <交付目录>/面试复盘报告.html \
  --preparation <工作目录>/准备记录.json --stats-output <工作目录>/渲染计时.json
```

所有题目、角色范围、引用都由渲染器校验。失败时按错误定位修改对应内容，保留已经正确的题目；不因此重新转写。内容质量仍须逐题审阅，脚本不能证明评价合理或未漏题。

4. 复用浏览器验收脚本：

```bash
node scripts/check_review.cjs --html <交付目录>/面试复盘报告.html \
  --transcript <交付目录>/转写稿.txt --artifacts <工作目录>/浏览器检查
```

默认抽查首、中、末题及其原文关联，全文原文仍逐一比对。模板、交互或渲染器变化时加 `--full` 检查全部题目与原文关联。脚本同时检查目录切换、选中状态、键盘操作、推荐答法始终展开和窄屏目录展开，保留桌面、手机截图和 `浏览器校验.json`；失败必须报告，不把未执行当作通过。查看截图确认可读性，发现问题再修复受影响部分。

## 浏览器依赖

需要 Node.js 与 Playwright。脚本依次尝试 `--playwright-module <模块绝对路径>`、`PLAYWRIGHT_MODULE`、当前 Node 环境、Codex 自带运行时和本技能缓存中的 Playwright，不依赖另一个 skill。默认使用本机 Chrome；使用 Playwright Chromium 时传 `--channel chromium`。

若没有可用的依赖，可在独立缓存安装：

```bash
npm install --prefix "$HOME/.cache/interview-audio-review/browser" playwright
```

使用本机 Chrome 无需下载 Chromium；若使用 `--channel chromium`，先运行缓存目录下的 `node_modules/.bin/playwright install chromium`。无可用浏览器且不能安装时，保留生成的文件，并明确说明浏览器检查未完成。

## 耗时解释

- 转写计时分别记录解码、模型加载、识别、写入和总时间。
- 渲染计时记录校验及 HTML 写入耗时；提供准备记录时，额外记录从准备完成到渲染结束的分析阶段墙钟时间，包含思考、编辑、工具调用和等待，不能解释为纯推理计算。
- 浏览器计时记录验收脚本从启动到完成的时间。
- 这些文件留在工作目录。按实际值解释本次运行，不根据录音时长承诺固定生成时间或提速倍数。

# 分析数据与原文关联

`分析.json` 是 UTF-8 工作文件，供渲染器读取，不作为交付物。字段示例：

```json
{
  "title": "面试名称",
  "date": "YYYY-MM-DD",
  "audio": "原始录音.m4a",
  "summary": ["整体评价，引用题号。"],
  "questions": [
    {
      "id": "q1",
      "title": "问题主题",
      "type": "项目经历",
      "brief": false,
      "question": "主问题、约束与追问的整理转述。",
      "answer": ["实际回答第一点", "实际回答第二点"],
      "evaluation": "判断、证据与影响。",
      "answer_basis": {"required": ["本题明确要求回答的内容"], "conditional": [], "optional": [], "information_gaps": ["录音缺少的个人事实"]},
      "steps": [{"title": "动作标题", "body": "简短说明。"}],
      "speech": "可连贯口述的推荐回答。",
      "uncertainty": ["术语或说话人待核说明。"],
      "evidence": [{"time": "00:01:12", "quote": "原文中的连续引文", "note": "与评价的关系。"}],
      "sources": [{"label": "来源名称｜支持的具体判断及适用版本或条件", "url": "https://example.com/source"}],
      "ranges": [
        {"start": "00:01:00", "end": "00:01:12", "role": "interviewer"},
        {"start": "00:01:12", "end": "00:02:00", "role": "candidate"}
      ]
    }
  ]
}
```

## 字段

- 必填：报告的 `title`、`date`、`audio`、`summary`、`questions`；每题的 `id`、`title`、`question`、`answer`、`evaluation`、`steps`、`speech`、`ranges`。列表不能为空，`steps` 的每项需有 `title`、`body`。
- `audio` 填写交付目录中的录音副本名称，如 `原始录音.m4a`。
- `recorded_at`（含时区的 ISO 日期时间）与 `duration_seconds`（正数秒数）可选，用于用户确认的录制时间与时长；缺省时渲染器尝试读取媒体元数据，不以文件系统创建时间或报告日期替代。标题将录制时间转换为本地时区并显示到分钟，时长四舍五入为约多少分钟；未知显示“未提供”。`storage_path` 由渲染器按 HTML 输出目录自动写入绝对路径。
- `id` 依次为 `q1`、`q2`……，题目按首次关联时间排序。`type` 是可选主题类别；`brief: true` 标记简单确认题。
- `uncertainty`、`evidence`、`sources` 可省略；关键评价保留证据用于校验，HTML 不另列证据区块。来源 URL 只允许 http(s)。

## 回答依据与复核

- `answer_basis` 是分析工作字段，现有模板不显示；新分析的重要题填写，简单事实确认题可省略。`required` 列主问题与追问的必要回应，`conditional` 列依赖题设的判断，`optional` 列有帮助但不能作为漏答依据的补充，`information_gaps` 列无法从录音确认的个人事实；不适用的列表留空。不输出隐藏评分、思维过程或虚构招聘标准。
- 写完后按这些依据审阅 `steps` 与 `speech`：必要回应是否覆盖；结论有无超出适用条件；取舍有无代价；新增个人陈述能否在原文找到依据。缺少真实材料时保留具体占位，不靠外部资料或常见做法补写经历。
- `sources.label` 简述来源支持的具体判断及必要条件，模板会原样显示。只填写实际阅读并支持该判断的页面，优先直达章节；使用企业面试指导时说明它仅支持表达方法，不代表本次面试评分或录用标准。没有外部事实核对需要时不强配来源。
- 关键事实核对及内容审阅由代理完成；当前渲染器只校验结构、原文引文和 URL 协议，浏览器检查只验证呈现与交互，均不能证明答案事实正确。

## 原文关联

- 顶层 `transcript_turns` 按原文顺序标注完整发言的起点，例如 `[{"segment_id":"l1","role":"uncertain"},{"segment_id":"l2","question_id":"q1","role":"interviewer"},{"segment_id":"l2","starts_with":"好的，我来介绍一下","question_id":"q1","role":"candidate"}]`。`segment_id` 使用阅读稿的原始片段 ID；`starts_with` 省略表示该块开头，填写时须是块内唯一出现、与原文完全一致的起始短语，不改写原文。每个起点持续到下一个起点，最后一个持续到全文结束；第一项从首块开头开始。
- 新分析填写 `transcript_turns`，旧分析缺省时仍兼容按同题、同角色合段。一个完整问题或连续回答可跨多个音频块，不能因字数、标点或静音阈值再拆段；实际追问、换人或换题另起。`question_id` 与所覆盖片段的 `ranges` 归属一致，未纳入分析的部分省略该字段；`role` 沿用下列枚举。短附和不打断主体发言时用 `mixed: true` 保留内部标记，展示时不加“含接话”后缀，角色仅指主体发言；归属不清则用 `uncertain`。
- 渲染器校验起点存在且递增、不跨题目归属；原文按起点切片后原序呈现。块内拆分仍使用原音频块的起止时间，每块首个切片保留原 ID，后续切片使用独立 ID 并记录原块 ID；浏览器验收按原块重组文字，确认无遗漏、重复或改写。
- `ranges` 使用半开区间 `[start,end)`，按原文片段的开始时间归属；端点优先用实际片段边界。每题可有不连续范围，不同范围不能重复占用同一片段。
- `ranges.role` 为 `interviewer`、`candidate`、`context` 或 `uncertain`。混合发言或身份不明用 `uncertain`，不能整块强归一人；更细的展示边界由 `transcript_turns` 表达。未关联片段仍保留为“未纳入分析”。
- `evidence.time` 必须落在本题关联片段上，`quote` 为对应发言去除空白后的连续引文；可跨同一角色的相邻片段，不能跨角色拼接。引文覆盖的片段须包含该时间，渲染器会检查。

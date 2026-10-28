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
      "steps": [{"title": "动作标题", "body": "简短说明。"}],
      "speech": "可连贯口述的推荐回答。",
      "uncertainty": ["术语或说话人待核说明。"],
      "evidence": [{"time": "00:01:12", "quote": "原文中的连续引文", "note": "与评价的关系。"}],
      "sources": [{"label": "来源名称", "url": "https://example.com/source"}],
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
- `id` 依次为 `q1`、`q2`……，题目按首次关联时间排序。`type` 是可选主题类别；`brief: true` 标记简单确认题。
- `uncertainty`、`evidence`、`sources` 可省略；关键评价保留证据用于校验，HTML 不另列证据区块。来源 URL 只允许 http(s)。

## 原文关联

- `ranges` 使用半开区间 `[start,end)`，按原文片段的开始时间归属；端点优先用实际片段边界。每题可有不连续范围，不同范围不能重复占用同一片段。
- `role` 为 `interviewer`、`candidate`、`context` 或 `uncertain`。混合发言或身份不明用 `uncertain`，不能整块强归一人。未关联片段仍保留为“未纳入分析”。
- `evidence.time` 必须落在本题关联片段上，`quote` 为对应发言去除空白后的连续引文；可跨同一角色的相邻片段，不能跨角色拼接。引文覆盖的片段须包含该时间，渲染器会检查。

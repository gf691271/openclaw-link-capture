---
name: link-capture
description: >
  链接知识捕获器。Frank（或任何agent）对话中出现URL时自动触发：
  抓取全文→摘要→打标签→去重检查→存入Nowledge Mem知识图谱。
  支持Twitter/X、网页文章、YouTube（摘要）。
  附带选题卡功能：关键词→搜知识库+社媒热度+历史去重→输出完整选题卡。
  激活词：任何URL（自动）；「选题 [关键词]」「选题卡 [关键词]」（手动）
version: 1.0.0
author: 银霜客
tags: [knowledge, capture, twitter, link, dedup, topic-card, nmem]
---

# Link Capture — 链接知识捕获器

## 核心哲学

> **每条链接都是一颗种子。不收进知识库，下次聊到就要重新找。**

Frank的习惯：对话中随手丢链接。
当前问题：用完即走，没有沉淀，下次还得重新搜。
这个skill解决：**链接进来 → 知识留下来。**

两个模式：
- **模式A — 捕获**：URL出现 → 自动抓取+存库（链接进来时触发）
- **模式B — 选题**：关键词 → 搜知识库+去重+热度 → 输出选题卡（主动查询时触发）

---

## 模式A：链接捕获管道

### 触发条件

对话中出现以下格式的URL时，**自动执行**（不需要用户说「帮我保存」）：

```
https://x.com/...          → Twitter/X 推文
https://twitter.com/...    → Twitter/X 推文  
https://t.co/...           → Twitter短链（先解析再处理）
https://youtube.com/...    → YouTube（抓字幕/描述，无字幕则存标题+描述）
https://*.substack.com/... → Newsletter文章
https://...（其他）        → 通用网页文章
```

**豁免**（不触发捕获）：
- 图片直链（.jpg/.png/.gif/.webp）
- Frank明确说「这个不用存」
- 重复URL（上次存过的，直接告知已有）

---

### 执行步骤

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP A1 — 内容抓取
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Twitter/X URL：
  → 调用 x-tweet-fetcher: 
    python3 skills/x-tweet-fetcher/scripts/fetch_tweet.py --url "<url>" --pretty
  → 提取：author, screen_name, text, likes, retweets, bookmarks, views, created_at

YouTube URL：
  → 调用 summarize skill（若已安装）
  → 或 web_fetch 抓取页面获取标题+描述+自动字幕
  → 无字幕则存：标题+频道+描述+URL

其他网页：
  → 调用 web_fetch(url, extractMode="markdown")
  → 截取前5000字（避免token浪费）
  → 提取：标题、作者/来源、发布日期、核心内容

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP A2 — 去重检查
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ 用标题+核心句子做 memory_search（maxResults=3）
□ 检查返回结果的相似度分数：
  - score > 0.85：高度重复 → 告知已有，跳过存储，显示已有记录链接
  - score 0.60-0.85：部分重复 → 告知相似内容，询问是否仍要存入（默认：存，但标注关联）
  - score < 0.60：新内容 → 直接存入

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP A3 — 自动标签生成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

根据内容自动推断标签（最多5个）：

主题标签（选1-2）：
  ai-agents | twitter | openclaw | real-estate | school-district
  robotics | content-strategy | engineering | immigration | career
  north-shore-crossing | zealty | dsr | arc | etl | family

来源标签（选1）：
  source-twitter | source-youtube | source-web | source-newsletter

信号类型标签（选1）：
  signal-tool | signal-insight | signal-news | signal-method | signal-data

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP A4 — 存入知识图谱
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

调用 nowledge_mem_save()：

title: "[来源] 标题（≤60字）"
  格式：
    Twitter: "[@screen_name] 推文核心观点（≤40字）"
    文章: "文章标题 — 来源名"
    YouTube: "[YouTube] 视频标题 — 频道名"

text: 结构化摘要，格式：
  来源：[URL / @作者 / 发布日期]
  核心观点：[2-3句话，提炼最有价值的信息]
  关键数据/金句：[数字、可引用的句子]
  与Frank相关：[为什么这对Frank有用，1句话]
  [如有代码/工具：工具名+用途]

unit_type: 按内容选择
  fact（工具/数据/事实）| learning（方法论/洞察）
  event（新闻/发布）| preference（Frank明确表态喜欢的）

labels: [上一步生成的标签]
importance: 
  0.8-1.0：Frank主动分享+高互动（likes>1000 or bookmarks>500）
  0.5-0.7：一般参考资料
  0.3-0.4：背景信息

event_start: 内容发布日期（不是存储日期）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP A5 — 回复确认（简洁）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

存储成功后回复（1-3行，不要废话）：

📌 已收入知识库
**[@MatthewBerman] OpenClaw作为公司OS：50亿token实战**
标签：#openclaw #ai-agents #signal-tool
[如有去重提醒：⚠️ 相似内容已有N条，已关联]
```

---

## 模式B：选题卡生成

### 触发

```
「选题 AI记忆系统」
「选题卡 Zealty」  
「围绕XX出个选题」
```

### 执行步骤

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP B1 — 知识库检索
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

memory_search(query=关键词, maxResults=8)
→ 提取已有内容：相关文章/推文/洞察 + 时间 + 重要性

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP B2 — 社媒热度探测
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

web_search(query="[关键词] site:twitter.com OR site:x.com", freshness="pw")
→ 检索最近7天Twitter上的热度
web_search(query="[关键词]", freshness="pw")  
→ 检索最近7天整体热度

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP B3 — 去重分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

对知识库里的已有内容检查：
□ 相似度 > 40%（score > 0.7）的内容标注「已覆盖」
□ 找出「还没人说的角度」（knowledge gap）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP B4 — 输出选题卡
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 选题卡输出格式

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 选题卡：[关键词]
生成时间：YYYY-MM-DD
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【知识储备】N条相关记忆
  · [标题1] — [日期] [重要性★]
  · [标题2] — [日期]
  · ...

【本周热度】
  Twitter：[热门推文/话题 1-2条]
  整体：[热门文章/事件 1-2条]

【去重雷达】
  ⚠️ 已被覆盖（>40%相似）：[角度列表]
  ✅ 空白角度（建议切入）：[角度列表]

【推荐选题】（3个，差异化）
  A. [标题]
     角度：[与已有内容的差异点]
     Hook：[开头第一句话]
     适合媒介：[Twitter/YouTube/Newsletter]
     
  B. [标题]
     ...

  C. [标题]
     ...

【最强Hook候选】
  · [具体句子，含数字/名字]
  · [具体句子，反直觉型]

【来源推荐】（直接可引用）
  · [来自知识库的N条最相关来源]
━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 与其他Skill的协作

```
x-tweet-fetcher  →  link-capture (A1抓取层)
web_fetch        →  link-capture (A1抓取层)
nowledge_mem_save →  link-capture (A4存储层)
memory_search    →  link-capture (A2去重 + B1检索)
web_search       →  link-capture (B2热度探测)
link-capture     →  DSR (提供E层来源)
link-capture     →  ARC (提供已有内容素材库)
```

**ETL定位**：link-capture是**持续的E层输入**。
DSR做一次性深度侦察（10-30个来源），link-capture做日常积累（每条链接进来都存）。
两者共享同一个Nowledge Mem知识库。

---

## 给Agent的操作规范

### 银霜客（主session）
- 凡Frank对话中出现URL，**直接执行捕获管道，无需告知「我要存了」**
- 存完后用一行确认（📌 格式）
- 大段分析内容（如本次的DSR尔湾报告），主动问：「要把这次分析的结论存进知识库吗？」

### 墨雀（moquebird session）
- 同样规则适用
- 额外：Twitter链接的`likes/bookmarks/views`写入存储，用于判断内容质量
- 高互动内容（views>100K or bookmarks>2000）自动标注 `importance: 0.8`

---

## 核心记忆

> **每条链接=Frank的注意力。注意力是稀缺资源，不存就是浪费。**

> **去重不是为了「不存」，是为了「找空白」。** 重复>40%不是拦截，是信号：
> 这个话题Frank已经有积累，下一篇内容应该往更深/更差异化的方向走。

> **选题卡的价值在「空白角度」**，不在「热门话题列表」。
> 热门话题任何人都能搜到，只有Frank的知识库能告诉他「我已经有什么，还缺什么」。

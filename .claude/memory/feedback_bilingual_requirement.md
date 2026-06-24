---
name: feedback-bilingual-requirement
description: All robot SDK tutorial text and code comments must include both Chinese and English inline
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f5b7060-3409-4793-9ac2-ab9be5da8666
---

All docs and code in /home/sucre/Code/robot must be bilingual (Chinese + English).

**Why:** User's explicit standing instruction: "所有的教程和代码注释，都提供英文翻译。后续新增文本也确保中英都有"

**How to apply:**
- Markdown docs: section headers get `(English Title)`, prose gets `> *English translation*` blockquotes, table columns use `中文 / English`
- Python files: module docstrings add English after Chinese; inline comments use `# 中文 / English`; function docstrings append English translation after the Chinese

This applies to every new addition, not just existing content.

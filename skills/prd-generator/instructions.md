# PRD Generator

Use this skill when the task is to turn a concise product requirements summary into a stable PRD in Markdown.

## Input Contract

- Read JSON input that follows `references/field-schema.json`.
- Treat the input as the source of truth.
- If an important field is missing, write `待确认` instead of guessing.

## Output Contract

- Output Markdown only.
- Follow the section order and headings from `references/prd-template.md`.
- Keep the writing concise, execution-oriented, and structured.
- Avoid filler, repeated restatements, and decorative language.

## Workflow

### 1. Validate input

- Confirm required fields exist and are non-empty.
- Normalize arrays, booleans, and short enums into readable Chinese.
- Ignore unknown fields unless they add implementation value.

### 2. Normalize requirements

- Merge semantically duplicate statements.
- Separate confirmed facts from suggestions.
- Convert verbose feature descriptions into atomic feature items.
- Group details into:
  - product overview
  - MVP features
  - future features
  - page and interaction design
  - technical constraints
  - non-functional requirements
  - scope boundaries

### 3. Render each PRD section

#### 1. 产品概述

- Fill product name, core problem, target users, and platform.
- Use one sentence for the core problem.

#### 2. 功能需求

- Render MVP features as a table with:
  - 功能名称
  - 功能描述
  - 用户价值
- Keep each row atomic enough to support later API or task decomposition.
- Put future features in a flat bullet list.

#### 3. 页面设计

- Describe only the pages, major modules, and key interactions needed for implementation.
- Keep visual style guidance brief unless the design language directly affects implementation.

#### 4. 技术规格

- Separate confirmed technical constraints from suggested implementation choices in wording.
- Examples:
  - Confirmed: “无需用户认证”
  - Suggested: “前端可采用 React 实现”

#### 5. 非功能需求

- Keep only actionable constraints such as performance, security, usability, compatibility, and rate limits.

#### 6. 项目范围

- Ensure “在范围内” and “不在范围内（本期）” do not overlap.
- Prefer concrete deliverables over vague statements.

## Writing Rules

- Default to short paragraphs, bullets, and tables.
- Do not repeat the same fact across multiple sections unless it is required for clarity.
- Do not turn UI decoration into long prose.
- Do not invent backend, data model, or API details unless they are explicitly provided.
- If the input implies a likely implementation choice but does not confirm it, label it as a suggestion.
- When a field is unknown and important, write `待确认`.

## Final Checks

- The PRD is complete and directly usable by product, design, and engineering.
- MVP features are represented in a table, not long paragraphs.
- The document is shorter and clearer than the raw input while preserving key decisions.
- No section contains obvious redundancy.

# Bonsai iPad Runtime Workspace Contract

## 1. Authoritative Workspace

唯一官方开发目录：

D:\codexSpace\bonsai-ipad-runtime

所有以下操作必须在该目录执行：

- 阅读源码
- 修改源码
- 添加文件
- 删除文件
- 运行测试
- git commit
- git push

禁止在其他目录开发 Bonsai。


## 2. Forbidden Workspaces

禁止使用：

C:\Users\*\.codex\worktrees\*

作为 Bonsai 开发目录。

禁止：

- Codex hidden worktree 开发
- 临时 clone 开发
- detached HEAD 开发
- 在隐藏 worktree 中产生正式 commit


## 3. Before Any Development

任何代码修改前必须执行：

```powershell
pwd
git branch
git status
git rev-parse HEAD
git remote -v
```

## 4. Documentation Entry

[docs/INDEX.md](docs/INDEX.md) is the documentation authority and navigation entry.

## 5. Quick / Full 性能开发准则

- 性能优化默认 Quick；围绕本轮优化假设设计，不能作为固定缩水版 Full。
- Quick 必须包含可比基线、真实设备测量、目标指标和必要副作用检查。
- Full 执行完整适用回归与认证，用于候选晋级、重要高风险变更和正式发布。
- 未经用户授权，不得把垂直优化扩大为认证平台、架构治理、文档重构或无关功能。
- 优先复用现有测试工具；默认只运行受影响的专项测试。
- 辅助遥测缺失与真实安全异常必须区分；可输出注明局限的 Quick 探索性结果，不能冒充 Full PASS。
- 必要安全保护不得绕过；不确定推理请求不得自动重放。
- Quick 不自动晋级候选或修改默认 Batch。
- 范围外问题保留证据并停止扩展，等待下一项明确任务。
- 每轮最终回答包含实际修改、真实测量结果或待测状态、副作用及下一步决策。

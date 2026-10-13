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

C:\Users\*\ .codex\worktrees\*

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
# Bonsai iPad Project Workspace Contract

## 1. Authoritative Workspace

唯一官方开发目录：

D:\codexSpace\iPad27B

所有以下操作必须在该目录执行：

- 阅读源码
- 修改源码
- 添加文件
- 删除文件
- 运行测试
- git commit
- git push

禁止在其他目录开发。

## 2. Forbidden Workspaces

禁止使用 C:\Users\*\.codex\worktrees\* 作为 Bonsai 项目开发目录。

禁止：

- 创建新的 git worktree
- 使用临时 clone
- 使用 detached HEAD 工作
- 在隐藏 worktree 中产生正式 commit

如果需要切换分支，必须在 D:\codexSpace\iPad27B 内部完成。

## 3. Before Any Development

任何修改前必须执行并报告：

pwd
git branch
git status
git rev-parse HEAD
git remote -v

必须确认当前路径为：

D:\codexSpace\iPad27B

## 4. Git Rules

所有正式 commit 必须来源于 D:\codexSpace\iPad27B。

禁止认为“Codex 完成修改”等价于“release branch 已更新”。

完成任务前必须验证：

- git log --oneline
- git status
- git branch -vv

## 5. Release Promotion Rules

任何 release 更新必须经过：

开发修改 → commit → 人工确认 → merge/cherry-pick → CI → artifact

禁止自动：

- merge
- cherry-pick
- push

## 6. Dangerous Operations

没有明确授权禁止：

- git reset --hard
- git clean -fd
- git worktree remove
- git branch -D
- git push --force
- 删除项目目录

## 7. Completion Criteria

任何任务完成必须满足：

1. 修改发生在官方 workspace
2. commit 位于官方 workspace
3. branch 正确
4. git status clean
5. CI 通过

## 8. Project Development Principle

Bonsai 使用：

Single Workspace
+
Explicit Branch
+
Verified Commit
+
CI Gate

禁止：

Multi Worktree Agent Workflow
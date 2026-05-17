# 给后续 AI / 维护者的说明

这个项目的 GitHub 仓库已经开启了 `main` 分支保护。下面用最简单的话说明这是什么意思，以及以后应该怎么改代码。

## 现在发生了什么

以前可以直接把代码推到 `main`：

```bash
git push origin main
```

现在不建议、也通常不能这样做了。

原因是 `main` 是项目最重要的主分支。开启保护后，GitHub 会先检查代码有没有问题，再允许合并进去。这样可以避免：

- 不小心把坏代码推到主分支。
- 不小心强制覆盖历史记录。
- 不小心删除 `main` 分支。
- 测试失败的代码进入主分支。

## 以后正确的改代码流程

每次要改功能或修 bug，请按这个流程：

```bash
git checkout main
git pull origin main
git checkout -b codex/简短说明
```

例如：

```bash
git checkout -b codex/fix-upload-limit
```

然后正常修改代码，测试通过后提交：

```bash
git add .
git commit -m "Fix upload limit"
git push origin codex/fix-upload-limit
```

推送后，到 GitHub 页面创建 Pull Request，简称 PR。

## PR 是什么

PR 可以理解成：“我准备把这个分支的改动合并到 `main`，请 GitHub 先检查一下。”

GitHub 会自动跑这些检查：

- `Test and build`
- `Analyze (python)`
- `Analyze (javascript-typescript)`

全部通过后，才可以把 PR 合并进 `main`。

## 如果检查失败怎么办

不要直接合并。

先打开失败的 GitHub Actions 日志，看是哪一步失败：

- Python 测试失败：本地运行

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
```

- 前端构建失败：本地运行

```bash
cd frontend
npm run build
```

修复后重新提交并推送同一个分支：

```bash
git add .
git commit -m "Fix CI failure"
git push origin codex/简短说明
```

PR 会自动重新检查。

## 如果只是我自己维护，还需要 PR 吗

需要。现在 `main` 已经被保护，推荐所有改动都走 PR。

这样虽然多一步，但可以防止误操作，也能让 GitHub 自动帮你测试。

## 后续 AI 工具应该注意

- 不要直接推送到 `main`。
- 新改动请创建 `codex/` 前缀分支。
- 改完后开 PR，而不是直接合并。
- 提交前至少运行：

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
cd frontend && npm run build
```

- 不要提交 API Key、`.env`、EPUB 原书、生成的输出文件、SQLite 缓存。
- 如果修改翻译提示词、术语表、目标语言或缓存逻辑，要特别注意缓存 key 是否需要变化。

## 当前主分支保护规则

`main` 分支现在要求：

- 必须通过 PR 合并。
- 必须通过 GitHub Actions 检查。
- 禁止 force push。
- 禁止删除分支。
- 管理员也受这些规则约束。

简短理解：`main` 是稳定版本，不能直接改；所有改动先进新分支，再通过 PR 合并。

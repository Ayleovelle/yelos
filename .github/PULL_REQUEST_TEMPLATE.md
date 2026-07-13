## 📝 描述 / Description

<!--请描述此项更改的动机：它解决了什么问题？（例如：修复了 XX issue，添加了 YY 功能）-->
<!--Please describe the motivation for this change: What problem does it solve? (e.g., Fixes XX issue, adds YY feature)-->

## 🛠️ 改动点 / Modifications

<!--请总结你的改动：哪些核心文件被修改了？实现了什么功能？-->
<!--Please summarize your changes: What core files were modified? What functionality was implemented?-->

- [ ] 这**不是**一个破坏性变更 / This is NOT a breaking change.
<!-- 如果你的更改不是一个破坏性更改，请在检查框内打“x” -->
<!-- If your change is NOT a breaking change, please check the checkbox above (put an 'x' inside the brackets) -->

## ✅ 检查清单 / Checklist

<!--如果分支被合并，您的代码将成为 Yelos 的一部分！在提交前，请核查以下几点内容。-->
<!--If merged, your code will be part of Yelos! Please double-check the following items before submitting.-->

- [ ] 😊 如果 PR 中有新加入的功能或破坏性变更，已经通过 Issue 与作者讨论过。/ If there are new features or breaking changes in the PR, I have discussed it with the authors through an issue first.
- [ ] 👀 本地 `pytest -q` 全绿（若改动涉及 `distill` extra，另跑 `pytest -q -m distill_extras`）。/ Local `pytest -q` passes (also run `pytest -q -m distill_extras` if the change touches the `distill` extra).
- [ ] 🧹 `ruff check .` 与 `ruff format --check .` 干净，无遗留问题。/ `ruff check .` and `ruff format --check .` are clean.
- [ ] 📦 我确保没有引入未声明依赖，或者引入的新依赖已按用途加入 `pyproject.toml` 对应分组（核心 / `dev` / `distill` / `ui`）。/ I have ensured no undeclared dependencies were introduced, OR any new dependency has been added to the correct `pyproject.toml` group (core / `dev` / `distill` / `ui`).
- [ ] 📚 若改动涉及公共 API（如 `yelos.session` / `yelos.server`）或用户可见行为，已同步更新 README（`README.md` + `README.zh-CN.md` 两份）与 `CHANGELOG.md`。/ If the change touches a public API (e.g. `yelos.session` / `yelos.server`) or user-visible behavior, both READMEs (`README.md` + `README.zh-CN.md`) and `CHANGELOG.md` are updated.
- [ ] 🧭 无关改动已剔除，diff 保持聚焦。/ Unrelated changes have been dropped; the diff stays focused.
- [ ] 😮 我的更改没有引入恶意代码。/ My changes do not introduce malicious code.

## 影响范围 / Impact

<!-- 是否破坏性变更 / 是否需要用户改配置 (yelos.config.json) / 是否涉及 stdio 与 streamable-http 两种传输 -->
<!-- Is this a breaking change / does it require config (yelos.config.json) changes / does it affect both stdio and streamable-http transports -->

## ❤️ CONTRIBUTING

- [ ] 🥳 我已阅读并同意遵守该项目的 [贡献指南](../CONTRIBUTING.md) / I have read and agree to abide by the [CONTRIBUTING](../CONTRIBUTING.md) guide of this project.

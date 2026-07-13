<!-- markdownlint-disable MD029 -->
# 🤝 为 Yelos 做出贡献

感谢您有兴趣为 **Yelos**（一个独立的持久性情感在场 MCP / Python 库）做出贡献！无论是修复 Bug，添加新功能，还是改进文档，您的每一次贡献都能让这个项目变得更好。

为了营造一个开放和热情的社区环境，我们采用了 [贡献者契约](CODE_OF_CONDUCT.md) 作为我们的行为准则。请确保您在参与贡献之前，已经阅读并同意遵守它。

在参与贡献之前，请仔细阅读以下指南：

## 📄 提交 Issue

### 🐛 报告 Bug

如果您在使用过程中发现了 Bug，请通过提交 [**Bug 报告**](../../issues/new?template=bug_report.yml) 来帮助我们。请在提交 Issue 之前：

1. **搜索现有 Issue**：检查是否已经有人报告过类似的问题。
2. **更新到最新版本**：确保您使用的是 Yelos 的最新版本，问题可能已经在新版本中修复。

### ✨ 提出功能建议 (Feature)

如果您对 Yelos 的库 API、MCP 工具集或配置项有任何绝妙的想法，欢迎通过提交 [**功能建议**](../../issues/new?template=feature_request.yml) 来与我们分享。请详细描述您的想法和它的使用场景。

### ❓ 使用咨询 / 问题讨论 (Discussion)

如果您暂时不能确定这是否是 Yelos 的 Bug，或者希望就库/MCP 用法、配置思路、与 `sylanne-core` 的联动排查等问题先进行讨论，欢迎提交 [**使用咨询 / 问题讨论**](../../issues/new?template=discussion.yml)。

### 📚 文档改进建议 (Docs)

如果您发现 README（`README.md` / `README.zh-CN.md`）、配置说明、API 文档或示例存在错误、缺失或表述不清的问题，欢迎提交 [**文档改进建议**](../../issues/new?template=docs.yml) 帮助我们持续完善文档体验。

### 🎨 设计 / 交互建议 (Design)

如果您对库 API 形状、MCP 工具划分与命名、配置项设计或可选 WebUI 面板的使用体验有改进想法，欢迎提交 [**设计 / 交互建议**](../../issues/new?template=design.yml) 与我们讨论。

## 💻 代码贡献

我们非常欢迎您直接通过代码来改进这个项目！**对于新功能的添加，请先通过 Issue 讨论。**

标准的贡献流程如下：

### 开发环境准备

0. 确保你要 `开发的功能` 或 `修复的问题` 没有与现有的最新进度重复。
1. Fork 本仓库到您的 GitHub 账号。
2. 克隆您的 Fork 仓库到本地：

    ```bash
    git clone https://github.com/your-username/yelos.git
    cd yelos
    ```

3. 确保您已安装 Python 3.10+。
4. 安装开发依赖（推荐用 [uv](https://docs.astral.sh/uv/)，也可以用 pip）：

    ```bash
    uv sync --extra dev
    # 或
    pip install -e ".[dev]"
    ```

    这会装好 `pytest`、`ruff`，以及测试所需的 `PyYAML` / `pytest-asyncio`。若要跑涉及
    `torch` 的 distill 额外档测试，另外 `pip install -e ".[distill]"`。

### 代码风格

为了保持代码的一致性和可读性，请遵循以下规范：

- **格式化**：使用 `ruff` 进行代码格式化和检查，`ruff format .` 与 `ruff check --fix .`，与 CI 中的 `ruff-format.yml` 保持一致。
- **类型注解**：尽可能为函数和类添加 Python 类型提示 (Type Hints)。
- **文档字符串**：为模块、类和函数编写清晰的 Docstring。

### 运行测试

```bash
pytest -q
```

测试覆盖 `core` / `primal` / `arbiter` / `intrinsic` / `shadow` / `finitude` / `memory` 等
模块。涉及 `torch` 的 distill 额外档用例标记为 `distill_extras`，装好 `[distill]` extra
后单独跑：

```bash
pytest -q -m distill_extras
```

### 提交 Pull Request (PR)

1. **创建分支**：从 `main` 创建一个新的功能分支。

    ```bash
    git checkout -b feat/your-feature-name
    # 或者
    git checkout -b fix/your-bug-fix
    ```

2. **提交更改**

- 编写代码并提交。我们鼓励您使用 AI 进行编码辅助，但请进行基本的 Review，并确保你知道自己在改什么。
- 提交更改时，请撰写清晰、描述性的提交信息，推荐遵循 [Conventional Commits](https://www.conventionalcommits.org/)（约定式提交规范），并与本仓现有提交历史的语言风格（英文）保持一致：
  - `feat`: 新功能
  - `fix`: 修复 Bug
  - `docs`: 文档变更
  - `style`: 代码格式调整（不影响逻辑）
  - `refactor`: 代码重构
  - `perf`: 性能优化
  - `chore`: 杂务

3. **推送到远程**：

    ```bash
    git push origin feat/your-feature-name
    ```

4. **发起 PR**：在 GitHub 上发起 Pull Request，指向 `main` 分支，参照 PR 模板详细描述您的更改内容和目的。如果您的更改涉及公共 API（如 `yelos.session` / `yelos.server`），请同步更新 README（EN + 中）与 `CHANGELOG.md`。
5. **代码审查**：等待维护者审查您的代码。如果有修改建议，请及时响应并更新代码。

> [!TIP]
> 提交 PR 前和进行开发时与仓库维护者提前交流可以提高你的 PR 被合并的概率 :)

## 📝 文档贡献

文档与代码同样重要。`README.md` 与 `README.zh-CN.md` 是双语维护的，如果您发现其中任何
一份（或 `CHANGELOG.md`）有错别字、表述不清、过时内容，或两份 README 之间出现了不一致，
欢迎直接提交 PR 进行修正。

---

## ❤️ 致谢

感谢所有为 Yelos 做出任何形式贡献的个人与团体，也感谢 `sylanne-core` 情感引擎 SDK 提供的
底层能力支撑。

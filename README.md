# Web 业务系统自动化测试与质量保障

基于开源 RealWorld Vue3 / Django Ninja 的独立 Python 测试工程。业务系统来自上游；本项目开发测试框架、用例、只读 SQL 校验、隔离环境启动器和 CI 配置。

正式用例 **35 条：27 API + 8 UI**，其中 **5 条包含数据库跨层校验**，不是额外增加 5 条。本地 BUG-001 补丁版本已实际通过全量测试。GitHub Actions 已在 **Ubuntu 24.04 x86_64 实际运行，35/35 通过，0失败/错误/跳过**。见 [真实云端运行](https://github.com/saberwwww/realworld-sdet-automation/actions/runs/41756762324)；仓库保持 Private。最新实际结果见 [阶段5报告](docs/stage-5.md) 和 [可公开统计](docs/verification-summary.json)。

## 快速复现

要求 Git、Python **3.13.7**、Node **22.18.0**（配套 npm **10.9.3**），网络可访问 GitHub、PyPI、npm、Playwright 下载源。启动器严格检查版本，避免悄悄使用另一套依赖。macOS ARM64 与 GitHub 托管 Ubuntu 24.04 x86_64 均已实际验证。

在工程根目录：

```bash
python3 scripts/bootstrap.py
python3 scripts/run_tests.py
```

Linux 首次安装浏览器系统包时使用（需要系统包安装权限）：

```bash
python3 scripts/bootstrap.py --with-browser-system-deps
python3 scripts/run_tests.py
```

bootstrap 自动检出固定源码、创建后端/测试两个虚拟环境、安装锁定依赖、执行 npm ci 和生产构建、安装 Chromium。已有源码 SHA 或跟踪文件不匹配时拒绝覆盖。无需手工先启动前后端；pytest fixture 会启动服务、轮询 HTTP 就绪、设置本地 VITE_API_URL，再运行测试。

```bash
python3 scripts/run_tests.py --suite api
python3 scripts/run_tests.py --suite ui
python3 scripts/run_tests.py --suite db
python3 scripts/run_tests.py --reverse
# 未修复基线，预期暴露 BUG-001，命令返回非零：
python3 scripts/run_tests.py --mode baseline --suite api
# 主动注入错误断言，验证失败截图/Trace；不是产品 Bug：
python3 scripts/run_tests.py --diagnostic ui
```

默认每次在 `.runtime/runs/<UTC时间戳>` 创建独立证据目录，也可指定 `--run-dir`（拒绝覆盖已存在目录）。结果包含 JUnit XML、summary.json、pytest.txt、前后端日志、清理证明；UI 失败保留截图和 Trace。

```bash
.venv-test/bin/python -m playwright show-trace /absolute/path/to/trace.zip
```

完整 Chromium 通道由 pytest.ini 固定；历史 macOS Headless Shell 点击超时记录见阶段3报告。没有使用固定浏览器 sleep 或降低断言规避失败。

## 隔离、安全与补丁

每个 pytest session 从固定后端 commit 导出临时副本，创建临时 SQLite。用户/文章唯一命名，文章经 API 清理；会话结束销毁数据库（含不能通过 API 删除的用户）。数据库只读查询，不访问开发数据库。每条 UI 测试创建独立 context，所有业务网络请求必须指向本地环境。

`fixed` 模式只向临时源码应用 [BUG-001.patch](patches/BUG-001.patch)，应用前执行 git apply --check。每轮重新导出，避免重复叠加；失败会明确报错。它是**本项目本地修复，未提交上游**。baseline 不应用补丁；两者使用同样严格的测试断言。原始缺陷记录及历史文件不改写。

原始证据可能包含临时测试 Token、密码和机器路径，`.gitignore` 排除 evidence、output、.runtime、数据库和环境文件；公开仓库只提供脱敏统计及文档。CI 按需求上传诊断证据，保留 7 天；Trace 仍可能含一次性测试凭据，不应与真实账户/密钥混用。历史原始证据仍保留在本机，忽略规则不会删除它们。

## CI 与边界

[GitHub Actions](.github/workflows/tests.yml) 在 push 到 main/master、PR 或手动触发时使用 Ubuntu 24.04，固定 Python/Node 和 action SHA；安装 Chromium 系统依赖，调用相同 bootstrap/run_tests 入口，always 上传已有证据。测试失败保持非零退出，不跳过认证测试。手动 baseline 模式预期红灯。

本机未安装 Docker/Podman；已获授权在 Private GitHub 仓库执行真实 CI。首轮27通过、8个UI启动错误，日志定位为 Chromium socket 临时路径过长；仅将启动器临时目录改为 /tmp/rw-*，修复后35/35通过。未修改测试标准、未改动上游源码或提交上游PR。详细失败与修复证据见阶段5报告。

## 项目导航

- [架构与数据流](docs/project-architecture.md)、[测试策略](docs/test-strategy.md)
- [最终阶段报告](docs/stage-5.md)、[面试深挖](docs/project-interview.md)、[简历素材](docs/resume-materials.md)
- [真实 BUG-001](docs/bugs/BUG-001-invalid-token-500.md)
- [UI 场景](docs/test-design-ui.md)、[数据库阶段](docs/stage-4.md)
- [第三方来源与许可证](THIRD_PARTY_NOTICES.md)

源码版本见 config/upstream.json；Python 和 npm 锁独立保存于 config/。上游业务源码不纳入个人成果；上游 JS Playwright 用例不作为本项目 Python 测试。未开发性能平台、通用测试管理系统或公网服务。

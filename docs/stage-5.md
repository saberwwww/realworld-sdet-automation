# 阶段5：CI、可复现性与交付

日期：2026-11-04。正式用例仍为27 API + 8 UI，其中5条跨层增强。未新增业务用例、未修改原始业务源码、未修改BUG-001历史证据、未Push/创建PR/部署。

## 完成范围

- 新增 .github/workflows/tests.yml：Ubuntu 24.04、Python 3.13.7、Node22.18.0，action固定commit；只读contents权限，checkout不持久化凭据。
- scripts/bootstrap.py 统一源码/依赖安装和前端构建；scripts/run_tests.py 统一调用pytest fixture，输出JUnit、JSON、日志，保留真实退出码。
- scripts/checkout_upstream.py 可重复验证已存在源码；拒绝SHA或跟踪文件漂移，避免reset覆盖用户改动。
- tests/support/server.py 补丁预检失败信息明确包含baseline SHA和git错误；补丁本身未改变。
- 完善 .gitignore、第三方许可证副本及来源说明、README、架构、策略、面试、简历材料。
- 开源业务代码归upstream；新增Python脚本/文档/CI归测试工程。Python依赖锁与35条正式测试的业务断言均未放宽。

## CI执行链

checkout → setup-python/setup-node → bootstrap（锁定源码、pip、npm ci、build、Chromium --with-deps）→ run_tests → pytest fixture启动本地后端/前端并等待HTTP就绪 → 真实API/UI/SQL断言 → teardown → JUnit汇总 → always上传已有证据。

显式bash保证pipefail，避免安装失败被tee掩盖。测试失败会使job失败；最后上传不改变测试退出码。只上传指定日志/报告/诊断目录，不上传整个.runtime、虚拟环境或临时数据库。artifact保留7天；原始Trace可能含一次性测试凭据，不能视为自动脱敏。

API/UI共用临时后端和数据库，VITE_API_URL由fixture传入，浏览器检查业务请求指向本地。后台服务没有独立的CI启动实现，不会出现本地和CI各维护一套服务逻辑。服务就绪采用截止时间内HTTP轮询；轮询间隔不是浏览器固定等待。

## 实际环境与兼容性判断

本地macOS ARM64，Python3.13.7。为贴近CI，在.runtime/node-runtime安装Node22.18.0/npm10.9.3，通过PATH选择，不替换系统Node25。前端依赖engine包含 ^22.18.0 或 >=24.11.0，故不选择过早的Node22小版本。

执行 npm ci --ignore-scripts --no-audit --no-fund 及生产build成功；未使用audit fix或依赖升级。官方pytest-playwright插件和完整Chromium channel保持不变；实际浏览器156.0.8078.4。生产build通过不代表对生产打包产物进行了UI测试，UI仍测试Vite服务。

下载并确认下列固定包有Linux x86_64可用wheel：Playwright1.64.1、greenlet3.5.6、psycopg2-binary2.9.11、pydantic_core2.50.2、MarkupSafe3.0.4。只做分发可用性检查，未将Linux wheel安装到macOS，更不等于Linux运行成功。

本机没有Docker/Podman/Colima等容器运行时；未为此安装系统工具。**Linux浏览器、系统包安装和GitHub Actions实际执行均尚未验证。** 使用官方Playwright的Chromium --with-deps方案，待授权后由真实runner验证。

## 实际命令与结果

在根目录安装本地匹配运行时（只影响.runtime）：

```bash
npm install --prefix .runtime/node-runtime --no-audit --no-fund node@22.18.0 npm@10.9.3
export PATH="$PWD/.runtime/node-runtime/node_modules/.bin:$PATH"
python3 scripts/bootstrap.py
.runtime/tools/actionlint .github/workflows/tests.yml
python3 scripts/run_tests.py --run-dir .runtime/stage5-fixed-1
python3 scripts/run_tests.py --run-dir .runtime/stage5-fixed-2
python3 scripts/run_tests.py --reverse --run-dir .runtime/stage5-reverse
python3 scripts/run_tests.py --mode baseline --suite api --run-dir .runtime/stage5-baseline
python3 scripts/run_tests.py --diagnostic ui --run-dir .runtime/stage5-diagnostic
```

actionlint1.7.7二进制下载后校验官方checksum，配置检查exit0。bootstrap exit0，pip check无依赖冲突，npm生产构建成功。

| 运行 | 通过 | 失败 | 错误/跳过 | JUnit时间 | 退出码 |
| --- | ---: | ---: | --- | ---: | ---: |
| fixed第1轮 | 35 | 0 | 0/0 | 16.353s | 0 |
| fixed第2轮 | 35 | 0 | 0/0 | 16.030s | 0 |
| fixed反序 | 35 | 0 | 0/0 | 15.492s | 0 |
| baseline API | 22 | 5 | 0/0 | 5.387s | 1 |
| UI诊断故障注入 | 0 | 1 | 0/0 | 6.012s | 1 |
| 新目录独立安装后全量 | 35 | 0 | 0/0 | 20.540s | 0 |

时间来自XML测试会话，不含bootstrap和wrapper开销，不代表性能指标。可公开统计及原始文件SHA256见 verification-summary.json。

新目录验证：复制scripts/config/tests/patches/pytest.ini到.runtime/cleanroom-stage5；bootstrap从公开仓库重新clone固定源码、创建全新.venv-backend/.venv-test、安装依赖与npm ci/build。仅将下载好的浏览器目录以软链接作为缓存复用，使用同一macOS宿主及Node；不是全新操作系统验证。

```bash
python3 .runtime/cleanroom-stage5/scripts/bootstrap.py
python3 .runtime/cleanroom-stage5/scripts/run_tests.py --run-dir .runtime/stage5-cleanroom
```

Linux wheel预检查命令：

```bash
.venv-test/bin/python -m pip download --dest .runtime/linux-wheels \
  --only-binary=:all: --no-deps --platform manylinux2014_x86_64 \
  --platform manylinux_2_17_x86_64 --platform manylinux_2_28_x86_64 \
  --python-version 313 --implementation cp --abi cp313 \
  playwright==1.64.1 greenlet==3.5.6 psycopg2-binary==2.9.11 \
  pydantic_core==2.50.2 MarkupSafe==3.0.4
```

五个wheel均下载成功；详细输出存 evidence/stage-5/linux-wheels.log。两个bootstrap日志和actionlint结果也保存在 evidence/stage-5。

## 补丁与红灯证据

fixed每轮从同一commit导出新副本，再git apply --check和apply，不在原始upstream源码上打补丁。连续/反序/新目录运行证明重复流程可用。额外在一次性副本连续检查同一补丁，第二次预检明确拒绝已应用补丁；记录 evidence/stage-5/patch-preflight.json。这样重复运行安全，不需要让git apply静默吞掉任何错误。

baseline的5个失败分别来自原有invalid-token和认证边界invalid、malformed-jwt、tampered-signature、expired；预期401实际500，同一根因的多个输入，不是5个新产品Bug。合法Token及其他API仍通过。没有skip、xfail或continue-on-error。

UI故障注入明确写错期望标题，测试退出1但summary.json/results.xml仍存在，截图和Trace均生成。ZIP完整性检查通过，包含trace事件和network记录。这是框架诊断演示，不是产品缺陷。证据在.runtime/stage5-diagnostic/artifacts/；未声称GitHub artifact上传已实际测试。

## 清理、安全核对

六轮均检查cleanup.json：后端停止、数据库删除、文章剩余0；wrapper拥有的tmp根目录删除。涉及UI的五轮均验证context创建/关闭数量一致、frontend停止、browser断连、无该浏览器目录的残留进程。全量会话创建的32个用户随临时库销毁，不使用任意数据库全库删除。

对待提交候选文件进行长JWT和私钥头有限模式扫描，无命中；git check-ignore验证.env、虚拟环境、.runtime、evidence、output、数据库和storage-state均被忽略。这不是完整密钥审计。原始历史证据留在本地，公开仅脱敏统计；补丁、文档、源码固定信息和MIT许可证可随工程交付。

## 当前限制与下一步

没有新发现的产品Bug。本阶段解决的是运行入口、补丁复现、退出码和证据交付问题。已有BUG-001仍是本地补丁，未确认上游后续版本是否修复。

Python锁固定版本但没有全部分发hash；Linux apt包随runner镜像变化；外网安装可能失败。未测试Windows、生产数据库、多浏览器、性能或生产静态部署。SIGKILL/断电无法保证Python finally，runner回收和限定临时目录提供额外隔离边界。

下一步需要用户确认目标GitHub仓库及Push授权，随后第一次实际运行固定补丁工作流、检查runner日志和artifact，记录run URL/commit，再更新“远程CI已验证”的状态。当前未创建远程仓库、未Push、未PR。

## 参考

- [Playwright Python官方CI说明](https://playwright.dev/python/docs/ci)：浏览器与Linux系统依赖安装。
- [GitHub Actions workflow语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)：触发、权限、shell、条件。
- [Node22.18.0版本说明](https://nodejs.org/en/blog/release/v22.18.0)：固定运行时及配套npm。

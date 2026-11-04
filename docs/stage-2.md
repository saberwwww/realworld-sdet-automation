# 阶段 2：接口自动化测试框架交付

> 历史快照：本文件描述阶段2当时的未修复状态。阶段2.5已完成本地补丁及回归，见 [阶段2.5报告](stage-2.5.md)。若要重现原20条历史测试，显式指定两个原测试文件及 `--backend-variant=baseline`；当前默认是修复版27条。

日期：2026-11-03（Asia/Shanghai）。阶段目标已实施和验证，但当前产品回归不是全绿：20 条正式实例中 19 通过、1 条稳定失败。失败保留为正常 FAILED，不 skip、不 xfail，不放宽预期。

## 对象、范围与契约

被测业务来自 upstream 中固定版本的 RealWorld Django Ninja。原始源码无修改；Python 依赖沿用阶段 1 锁文件，无新增依赖、无 npm 升级。

以 `config/upstream.json` 指定的规范子模块 `specs/api/openapi.yml` 为状态码依据，并核对 `apps/accounts/api.py`、`apps/articles/api.py`、对应 schemas 和实际结果。发生差异时保留契约失败，不能用实际错误结果覆盖规范。

| 场景 | 参数化后数量 | 预期 |
|---|---:|---|
| 注册成功、登录并用登录 Token 查询自己 | 2 | 201 / 200，身份字段匹配 |
| 非法邮箱、缺少密码、缺少用户名 | 3 | 422，字段错误列表 |
| 重复邮箱、重复用户名 | 2 | 409，对应字段错误 |
| 错误密码、用户不存在 | 2 | 401，credentials 错误 |
| 无 Token、无效 Token 查询自己 | 2 | 401；无效 Token 实际 500 |
| 文章创建→查询→修改→再查→删除→再查 | 1 | 201 / 200 / 204 / 404，字段和空响应验证 |
| 创建空标题、缺少 description、缺少 body | 3 | 422，字段错误 |
| 修改空标题并确认原文未变 | 1 | 422 |
| 未登录创建、修改并确认原文未变 | 2 | 401 |
| 非所有者修改、删除并确认原文仍在 | 2 | 403 |
| 总计 | 20 | 11 条用户/鉴权 + 9 条文章 |

CRUD 中的多次请求是一个业务链路测试实例；其他测试自行创建前置资源，不依赖这条用例的结果。本阶段不含收藏/关注/评论、全字段边界、标题变更导致的 slug 变化、分页、过期 Token、并发、SQL 业务一致性或 UI 测试。

## 目录及设计

```text
config/                         固定上游 SHA 和依赖锁（沿用）
upstream/                       开源业务仓库（不计自编代码）
tests/
  conftest.py                   fixture、报告目录选项、反序收集选项
  support/
    client.py                   单一 HTTP Client，显式 Token，10 秒超时
    data.py                     UUID 用户/文章数据
    assertions.py               状态、JSON、用户、文章及错误断言
    server.py                   临时数据库、迁移、后端进程、清理审计
  api/
    test_users.py               11 条用户/鉴权实例
    test_articles.py            9 条文章实例
  demos/test_reporting.py       独立故障注入，默认不收集
scripts/summarize_junit.py       标准库解析 JUnit，区分 passed/failure/error/skipped
evidence/stage-2/                每轮日志、JUnit、清理记录及汇总
```

避免为每个接口单独建 Service 类，也不做重试、全局可变 Token、Excel 用例引擎。请求封装只负责传输；断言层表达契约；fixture 负责生命周期；业务测试保留可读的请求顺序。

## 隔离与清理的实际结果

每次 pytest 自动创建独立 TemporaryDirectory 和 SQLite 文件，运行迁移，以随机回环端口启动真实 Django 后端；不使用环境中的 API_BASE_URL，也不连接原演示数据库。每条用例创建独立 UUID 数据和 HTTP Session。

article_factory 在成功创建后登记 slug/作者 Token，测试失败后仍尝试清理所有登记文章。清理阶段允许 204 或 404，错误会作为 teardown ERROR 展示。session 最后停止自己创建的后端进程，使用只读 SQL 统计用户、文章、标签，再清理自己创建的临时目录；无全库 DELETE、无用户 ORM 删除。

两次正常顺序及一次反序运行：每轮销毁前均为用户 17、文章 0、标签 0；数据库销毁、进程停止均 true。用户保留到会话结束，是因为 API 不提供用户删除；数据库被销毁后用户与认证会话也不再残留。

故障注入轮创建了 1 用户和 1 文章，断言失败后文章仍清到 0，数据库仍销毁。独立缺陷复现无需用户，销毁前计数全为 0。各轮 cleanup.json 记录了不同临时数据库路径。

未观察到顺序依赖：两次顺序、一次反序结果一致，已知失败单独执行仍能复现。这不是所有排列或并发执行的形式证明。当前未使用 pytest-xdist。

## 实际执行与结果

从工程根目录执行；每条命令均独立运行，即使上一条有 FAILED 也继续下一条验证：

```bash
.venv-test/bin/python -m pytest -v --evidence-dir=evidence/stage-2/run-1 --junitxml=evidence/stage-2/run-1/results.xml
.venv-test/bin/python -m pytest -v --evidence-dir=evidence/stage-2/run-2 --junitxml=evidence/stage-2/run-2/results.xml
.venv-test/bin/python -m pytest -v --reverse-order --evidence-dir=evidence/stage-2/reverse --junitxml=evidence/stage-2/reverse/results.xml
.venv-test/bin/python -m pytest 'tests/api/test_users.py::test_protected_user[invalid-token]' -v --evidence-dir=evidence/stage-2/bug-repro --junitxml=evidence/stage-2/bug-repro/results.xml
.venv-test/bin/python -m pytest tests/demos -v --evidence-dir=evidence/stage-2/injection --junitxml=evidence/stage-2/injection/results.xml
.venv-test/bin/python scripts/summarize_junit.py evidence/stage-2/run-1/results.xml evidence/stage-2/run-2/results.xml evidence/stage-2/reverse/results.xml evidence/stage-2/bug-repro/results.xml evidence/stage-2/injection/results.xml > evidence/stage-2/summary.json
```

各 pytest 终端输出保存为相应的 `evidence/stage-2/<轮次>.txt`。此前首次开发验证结果另存 initial，不替代最终运行证据。

| 轮次 | 通过 | 失败 | 跳过 | 环境/清理错误 | JUnit 总秒数 |
|---|---:|---:|---:|---:|---:|
| run-1 | 19 | 1 | 0 | 0 | 3.864 |
| run-2 | 19 | 1 | 0 | 0 | 3.804 |
| reverse | 19 | 1 | 0 | 0 | 3.843 |
| bug-repro | 0 | 1 | 0 | 0 | 1.137 |
| injection | 1 | 1 | 1 | 0 | 1.202 |

正式每轮通过率 19/20 = 95%，不是所有功能覆盖率。耗时包含环境准备和清理，不是接口性能指标。injection 不计入业务通过率；SKIPPED 是刻意演示，不是隐藏未实现的业务测试。summary.json 同时保留每条用例的状态、耗时和失败原因；报告能区分通过、失败、跳过，并预留 error 分类。

## 真实问题与框架技术问题

真实产品问题 BUG-001：无效 Token GET /api/user 返回 500，而不是规范的 401。主 API 未捕获 jwt_ninja.errors.APIError，见 `docs/bugs/BUG-001-invalid-token-500.md`。未修复、未伪造修复后回归；本次不修改上游业务源码。

独立注入：创建成功后故意要求 HTTP 418，实际得到 201，日志明确包含方法、URL、预期和实际。用于验证故障定位和失败后的资源释放，不是产品 Bug。

框架实现时解决的问题：

- API 不支持删除用户：每轮新建临时环境，避免危险的全库清空。
- 清理不能只写在测试末尾：改为 yield fixture 和 finally；提前失败仍能释放已登记资源。
- 删除用例与 teardown 都会删除同一文章：业务断言严格 204，teardown 接受已经不存在的 404。
- 本机存在代理设置：本地请求 Session.trust_env=False，避免回环流量发给代理。
- 测试参数展开可能泄露凭据：默认短 traceback，不打印响应 Token/密码，不启用 showlocals；服务日志保留请求路径和异常栈。
- 阶段 1 手动运行的服务不应被测试误用：阶段 2 自管独立后端，忽略外部 API_BASE_URL。

## 已知工程限制

- 上游真实 Bug 导致默认回归非全绿；没有用 xfail/skip 遮蔽。
- SQLite 与 PostgreSQL、DEBUG 与生产模式不等价；只验证当前 macOS/Python 锁定环境。
- 随机端口采用“探测空闲后启动”，仍有很小的端口竞争窗口；若竞争发生会报启动错误，不会自动重试掩盖。
- SIGKILL、断电无法保证 finally 执行。只可核对报告中的本次临时路径后处理，不应扫描删除所有临时数据库。
- 默认证据目录会覆盖上次日志；保留证据应显式指定不同 --evidence-dir 和 XML 路径。
- 测试数据当前不带标签，未验证标签相关生命周期。SQL 仅用于清理审计，不声称实现了接口与数据库字段一致性测试。
- 原先 npm 的 8 项中危依赖告警仍未处理；本次没有运行 audit fix 或升级。

下一步建议先在另行确认的修复分支处理 BUG-001 并回归，再完善 API 数据边界与数据库一致性校验。本次到此停止，没有 UI 自动化、CI 或性能平台、远程 Push、公网部署。

# 阶段 0 / 1 验证记录

验证日期：2026-11-03（Asia/Shanghai）。本记录仅覆盖本机，不代表跨平台验证。

## 阶段 0：环境和可行性

已读取两仓库 README、后端 pyproject.toml / settings.py / accounts API、前端 package.json / vite.config.js，以及固定 RealWorld 子模块的 OpenAPI 和 malformed-email 示例。

实际环境：macOS 26.0 ARM64；Python 3.13.7；Git 2.50.1；Node 25.2.1；npm 11.6.2；Bun / Docker 命令不存在。选择 Python venv + npm + SQLite，使用真实业务代码和持久化数据库。

| 实际执行命令 / 操作 | 结果 / 证据 |
|---|---|
| `uname -a`、`sw_vers`、各工具 `--version` | `evidence/environment.json` |
| `git clone` 两个指定仓库 | 成功，固定 commit 见 `config/upstream.json` |
| `git -C upstream/frontend submodule update --init` | 下载必需样式和规范，固定子模块 commit |
| `python3 -m venv .venv-backend` / `.venv-test` | 两个独立环境创建成功 |
| `.venv-backend/bin/python -m pip install -r config/backend-sqlite.in` | 首次清单省略 psycopg2，安装成功但启动失败；清单现已修正 |
| `.venv-test/bin/python -m pip install pytest requests` | 成功；完整版本已 freeze |
| `bash scripts/backend.sh check` / `migrate`（初次） | `ModuleNotFoundError: No module named 'psycopg2'`，原始失败日志已保存 |
| `.venv-backend/bin/python -m pip install psycopg2-binary==2.9.11` | 成功；重新 freeze 锁定版本 |
| `bash scripts/backend.sh check` / `migrate`（重试） | check 无问题；迁移全部成功，见 `evidence/backend-check.txt` / `migrate.txt` |
| `npm --prefix upstream/frontend install --ignore-scripts` | 安装 183 packages，报告 8 moderate 告警 |
| `npm --prefix upstream/frontend run build` | exit 0，364 modules，`evidence/frontend-build.txt`；此处仅验证构建，未部署 dist |
| `bash scripts/backend.sh run` / `bash scripts/frontend.sh` | 分别在 127.0.0.1:8000 / :8080 启动 |
| Chrome 打开 `http://127.0.0.1:8080/` | Conduit 首页正常渲染，空文章列表；截图 `evidence/frontend-home.png` |
| requests GET `/docs`、`/api/tags`、`/api/articles` | 均 200；后两者分别为 tags=[]、articles=[] / articlesCount=0 |
| requests POST `/api/users` 后 POST `/api/users/login` | 201 / 200，同一测试用户；脱敏结果 `evidence/api-smoke.json` |

初始 clone 在受限执行环境无法访问本机代理；获准网络执行后成功，未修改用户全局代理配置。SQLite 路径固定在 `.runtime/`，未使用已有业务数据库。

psycopg2 问题属于本项目初次依赖裁剪错误：上游 `helpers/exceptions.py` 无条件导入 `psycopg2.errors.UniqueViolation`。不要把它包装成已发现的上游业务 Bug。安装 binary 包后导入、迁移、HTTP 注册均验证成功，业务源码未修改。未验证 PostgreSQL 或原始 psycopg2 2.9.6 的完整安装路径。

阶段 0 新增工程文件：`scripts/backend.sh`、`scripts/frontend.sh`、`scripts/checkout_upstream.py`、`config/`、`.gitignore`、说明和证据文件。上游源码不纳入自编代码量；其许可证保留在原仓库。前端 npm 额外生成 package-lock，锁文件另存于 config。

阶段 0 知识点：进程与端口、前后端 API 基地址、CORS、数据库 migration、依赖隔离、固定版本与可复现性。面试时重点解释 `backend.sh` 的 DEBUG / DATABASE_URL、为何无需 Docker，以及“pip 安装成功”为什么不等于“服务能运行”。

## 阶段 1：最小 API 测试

新增测试工程代码：`tests/conftest.py`、`tests/api/test_users.py`、`pytest.ini`、`examples/failure_demo.py`。测试仅依赖 pytest + requests，不导入 Django，不 mock 网络。

测试设计：

| 用例 | 输入 | 预期 | 实际 |
|---|---|---|---|
| test_register_user | UUID 用户名 / 合法邮箱 / 密码 | 201，user 对象，身份字段匹配，token 非空，无 password | PASSED |
| test_register_rejects_invalid_email | 非法邮箱，其余字段合法 | 422，errors.email 为非空字符串列表，无 user | PASSED |

基准是规范，不是“运行后看见什么就断言什么”。状态码来自 OpenAPI /users，错误字段来自规范示例；异常测试按预期被拒绝属于测试通过。

实际执行：

```bash
.venv-test/bin/python -m pytest -v --durations=5 --junitxml=evidence/pytest-results.xml
# exit 0: 2 passed in 0.15s

.venv-test/bin/python -m pytest examples/failure_demo.py -v
# exit 1: assert 422 == 201; 1 failed in 0.11s
```

完整输出分别为 `evidence/pytest-pass.txt` 和 `evidence/pytest-intentional-failure.txt`。正式套件本次 2/2 通过（100%），仅代表这两个用例；0.15 秒是 pytest 本次总耗时，不是接口性能指标。JUnit XML 保存了用例和执行耗时。失败示例独立执行，不纳入正式通过率。

重点掌握：

1. `http` fixture 使用 `with requests.Session()` 和 `yield`，测试结束后释放连接；为什么用例之间不共享登录状态。
2. `new_user` 的 UUID 如何避免重复注册冲突；唯一性不等价于清理，当前用户记录仍保留。
3. `api_url` 的环境变量与默认值；为什么 `trust_env=False` 可避免本机代理影响回环请求。
4. 两个 test 函数的 Arrange / Act / Assert；`json=` 与 `data=` 区别；timeout 防止无限等待。
5. HTTP 状态码、Content-Type、JSON 类型、业务字段各解决什么问题；不能仅断言 200。
6. pytest 如何发现测试、注入同名 fixture、展示 assert 差异；`testpaths` 如何排除故意失败示例。
7. 区分被测业务异常（422）、错误断言、服务不可达（连接错误）和 fixture 准备失败；不能都叫产品 Bug。

## 当前限制和下一阶段建议

- npm 安装报告 8 项中危依赖告警，保存 `evidence/npm-audit.json`；未自动升级，也未验证可利用性。
- Vite 提示未来 native config loader 不支持当前配置格式，当前 serve/build 已成功。
- 没有自动清理用户；没有 SQL 数据一致性断言；SQLite 不能代表 PostgreSQL 语义。
- 浏览器仅做一次首页可行性观察；注册和登录通过 HTTP 验证，不是 UI 业务回归。
- 未发现并完成真实业务缺陷的修复闭环，不能将教学失败当作 Bug。
- 复现脚本和版本锁已经提供，本次未在另一台干净机器上重装验证。

下一阶段建议先扩展登录、身份认证和文章 CRUD 的接口链路，设计 fixture 数据准备 / 清理与参数化边界测试，再加入 SQLite 查询一致性校验。确认后再实施；本次停止在阶段 0 / 1，没有 UI 自动化工程、测试平台或 CI，没有远程 Push、发布部署或付费服务。

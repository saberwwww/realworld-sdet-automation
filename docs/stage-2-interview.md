# 阶段 2：结合本项目练习面试

> 历史快照：本文件描述阶段2当时的未修复状态。阶段2.5已完成本地补丁及回归，见 [阶段2.5报告](stage-2.5.md)。若要重现原20条历史测试，显式指定两个原测试文件及 `--backend-variant=baseline`；当前默认是修复版27条。

先讲清事实：这是基于开源 RealWorld 的独立 HTTP 测试工程，不是自己开发的业务系统。20 个正式测试实例包含一个稳定复现的产品失败，不能说“20 条全部通过”。本项目不包含 UI 自动化和 CI。

## 1. pytest 怎样发现并执行测试函数？

从工程根目录执行 `.venv-test/bin/python -m pytest -v`，pytest 读取 `pytest.ini`。`testpaths = tests/api` 把默认收集范围限制为业务测试目录，然后按 `test_*.py` 文件和 `test_*` 函数收集测试。`tests/demos` 中的教学失败不会混入默认统计。

以 `test_login_user(api, owner)` 为例：pytest 看到参数名 `api`、`owner`，就查找同名 fixture。先准备 fixture 及其依赖，再执行函数体，最后清理。不是 Python 自动给函数参数赋值，是 pytest 做了这层调度。

`test_register_invalid` 只有一个函数，但三个参数组合会生成三个独立的测试实例；所以统计的是 collected items，不是源文件中的函数数量。

自己试：

```bash
.venv-test/bin/python -m pytest --collect-only -q
.venv-test/bin/python -m pytest tests/api/test_articles.py::test_article_crud -v
```

`--collect-only` 只收集，不会创建数据库或发请求。以上是练习命令；本次已执行命令和结果以阶段报告为准。

## 2. fixture 有什么用？yield 前后分别做什么？

在 `tests/conftest.py` 看 `api`：先构造 ApiClient，`yield client` 将它交给测试，测试完成后执行 `client.close()`。即使用例断言失败，pytest 仍会走正常 teardown。

`article_factory` 更接近企业项目：yield 之前创建资源登记列表和内层 create 函数；测试拿到 create 函数后可以创建文章；yield 之后遍历登记列表，以作者 Token 删除文章。清理收集错误后统一报告，避免第一条删除失败就放弃剩余文章。204 表示成功删除，404 表示业务测试已经删除；这两个码只在清理阶段都可接受，正常删除业务断言仍严格要求 204。

`api_url` 是 session scope：一次 pytest 运行共用一台临时后端，但每次运行都新建数据库。`owner`、`api` 默认 function scope：每个测试实例拿到新用户、新 HTTP Session。fixture 会按依赖关系组织执行，并不依赖源代码排列顺序。

注意边界：yield 前的准备工作失败，不能指望 yield 后代码运行。本项目环境管理用 contextmanager 的 try/finally 覆盖迁移、启动、运行和停止；SIGKILL 或断电仍不能保证清理。

## 3. 参数化怎样实现？

看 `test_register_invalid`：

```python
@pytest.mark.parametrize("field,value", [
    ("email", "not-an-email"),
    ("password", None),
    ("username", None),
])
```

pytest 把每个元组分别赋给 field 和 value。这里 None 是测试数据中的“删除字段”标记：代码用 `pop(field)` 真正删除键，测试的不是 JSON null。每个参数实例都会重新调用 new_user fixture，因此不会修改下一组参数的用户字典。

`ids` 为报告提供可读名字，比如 missing-password。适合参数化的是请求结构和断言逻辑相同、只有输入组合不同的场景；完整 CRUD 流程不必拆成巨大的参数表。

你需要能解释元组解包、字典 pop、条件分支，以及为什么浅拷贝嵌套字典时可能仍共享内部对象。当前 make_user 每次创建全新字典。

## 4. requests 怎样携带 Token？

看 `tests/support/client.py` 的 `ApiClient.request`：

```python
headers = dict(kwargs.pop("headers", {}))
if token is not None:
    headers["Authorization"] = f"Token {token}"
```

RealWorld 使用 Authorization 请求头；这里按其规范使用 Token 前缀。Token 从注册或登录响应取得，不硬编码真实用户的凭据。`test_login_user` 会把登录得到的 Token 用于 GET /user，并验证返回身份，证明这个 Token 不只是一个非空字符串。

Token 每次显式传入，不把它放入共享 Session 的默认 headers；这样无 Token 测试不会意外继承前一个用户的登录态。`json={...}` 让 requests 序列化 JSON 并设置 Content-Type；`timeout=10` 限制连接/读取等待，不等于整个测试必须在 10 秒内完成。

## 5. 为什么不能只判断 HTTP 200？

创建应为 201，删除应为 204，参数错误应为 422，无认证应为 401，越权应为 403，删除后查询应为 404。全部断言 200 会把正常行为判错。

即使返回了正确状态码，也可能是错误用户、字段缺失或“修改返回成功但没保存”。本项目在 `user_response` 校验用户名、邮箱、Token 和禁止 password 回传；在 `article_response` 校验正文、描述、标签和作者；修改之后再次 GET；越权请求之后再次 GET，确认原内容仍在。204 没有 JSON，必须检查空 body，不能无条件调用 response.json()。

这些还是有限断言：没有完整 JSON Schema 验证，没有自动证明数据库事务、并发或所有业务规则都正确。

## 6. 怎样保证测试互不影响？

本项目使用三层隔离：

1. 每个 pytest 进程新建专属临时 SQLite 和随机回环端口，不连接阶段 0 的演示数据库。
2. 每条测试使用 UUID 用户名、邮箱和标题；同一条测试里的 owner / stranger 是两个用户，其他测试不复用它们。
3. 文章由 fixture 登记并删除。用户接口没有删除能力，因此运行结束后停止子进程、只读统计资源，再销毁本次创建的临时目录。

没有“DELETE FROM 所有用户”一类逻辑。清理报告保留销毁前用户数量，说明用户确实存在过，再用 database_removed 表示数据库已销毁。文章应先通过业务 API 清理至 0；否则 session teardown 会报错，不能用数据库销毁掩盖文章清理失败。

本次连续运行、反序运行结果一致；已知无效 Token 问题单独运行也失败，没有观察到顺序依赖。反序并不能数学上证明所有随机顺序都独立，目前也没验证并发运行。

## 7. 接口测试失败怎样排查？

按“定位请求 → 对照规范 → 看环境 → 看业务日志 → 最小复现”的顺序。

真实例子：`test_protected_user[invalid-token]` 报告 GET /api/user 期望 401、实际 500、Content-Type 为 text/plain。首先确认规范要求认证失败返回 401；再看同一轮其他请求成功，排除整体服务未启动；查看对应目录 backend.log，定位到 `helpers/jwt_utils.py` 抛出的 `APIError('invalid_token', 401)`；检查主 NinjaAPI 的异常处理器，发现没有注册此类型处理；最后只执行这个 node id，仍然 500。

不要因为响应里某处带 401 就认为 HTTP 状态码是 401；异常对象的属性和真正发出的 HTTP 状态码是两件事。这个问题尚未修复，上游代码没有改动，回归闭环尚未完成。

再对比教学注入：`tests/demos/test_reporting.py` 故意对成功创建文章要求 418，报告清楚显示 POST /articles expected 418 got 201；原因是测试断言被故意改错，不是产品 Bug。

遇到 ConnectionError 先查进程、端口、代理；遇到 JSONDecodeError 查 Content-Type 和服务日志；遇到 fixture ERROR 查准备/清理流程。`scripts/summarize_junit.py` 将 error、failure、skipped 分开统计。默认使用短 traceback，避免在 fixture 参数展开时输出 Token；不要随意加 `--showlocals` 或打印完整响应。

## 8. 哪些 Python 函数应能脱离 AI 写出来？

建议按以下顺序练习，并能解释每行代码：

| 要独立写出的内容 | 项目对应位置 | 必须掌握 |
|---|---|---|
| 返回唯一用户字典的函数 | `make_user` | import、函数返回值、UUID、f-string、dict |
| 发一个带 Token 的 JSON 请求 | `ApiClient.request` | class/self、可选参数、关键字参数、字典、`**kwargs` |
| 校验响应和提取字段 | `json_response`、`error_response` | assert、类型判断、dict.get、列表、all、错误消息 |
| 准备用户并返回认证信息 | `user_factory` 内层 create | 闭包、函数作为返回值、字典展开、接口依赖 |
| 自动释放 HTTP Session | `api` fixture | yield、资源生命周期、fixture 注入 |
| 登记和逐项清理资源 | `article_factory` | list.append、元组解包、reversed、try/except |
| 从 XML 统计结果 | `summarize` | 文件路径、遍历、int/float 转换、JSON 输出 |

推荐一次 30 分钟练习：不看实现，写“注册→登录→携带 Token 查询自己”，再手动把密码改错，检查失败信息。第二次写文章创建和 finally 删除。先能独立写直线脚本，再提炼 fixture，不需要背整个临时服务管理器。

`isolated_backend` 涉及 subprocess、contextmanager、socket、超时和 finally，面试应讲清设计与风险，不必声称自己从零熟练实现了完整进程管理平台。

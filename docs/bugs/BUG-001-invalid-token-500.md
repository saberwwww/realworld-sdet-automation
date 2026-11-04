# BUG-001：无效 Token 访问用户接口返回 500

状态：**本地补丁已修复并完成回归**。原始上游 commit 仍保留缺陷；没有向上游提交、Push、PR 或部署。闭环成立于本次固定依赖、macOS、SQLite、DEBUG=True 环境，不代表上游官方已修复。

## 1. 问题描述和发现方式

阶段 2 的真实 HTTP 自动化测试 `test_protected_user[invalid-token]` 检查 GET /api/user：规范期望 401，实际为 500。最初 20 条测试中 19 通过、1 失败。不是主动注入，不是修改断言制造的缺陷。

阶段 2.5 重新阅读原测试、请求封装、API 规范、TokenAuth、jwt_ninja 解码和已安装 Django Ninja 异常分发代码。并用新的独立环境再次复现，未仅凭 500 推断根因。

## 2. 测试环境和来源

- 后端原始仓库：`https://github.com/c4ffein/realworld-django-ninja`。
- 固定 commit：`87dd078c883a046f5ff20269df2fb004d8b5f83f`。
- RealWorld 规范 commit：`25588846c314b15a5e427ffe816e6b4af7be68c7`。
- Python 3.13.7、Django 5.2.1、django-ninja 1.4.1、jwtninja 1.1.0，完整版本见 config/backend-sqlite.lock.txt。
- 每轮新建临时 SQLite，迁移后启动随机回环端口，DEBUG=True；数据库、源码副本和子进程结束后清理。
- 修复实验采用独立 `patches/BUG-001.patch`；每轮先 git archive 固定 commit，fixed 变体再对临时源码应用补丁。baseline 不应用补丁。原始 upstream/backend 工作区已核对保持干净。
- 证据目录：`evidence/stage-2.5/`。provenance.json 保存关键文件 SHA256，cleanup.json 保存基线 commit、变体和补丁 SHA256。

## 3. 请求、契约和最小复现

```http
GET /api/user
Authorization: Token not-a-valid-jwt
```

ApiClient.request 只在 token 非 None 时拼接 `Token ` 前缀。这个前缀与 OpenAPI securitySchemes.Token 的要求一致；无效字符串是刻意测试的用户输入，不是拼错合法账号的 Token。缺少 Token 和合法 Token 对照都能得到预期结果。

固定规范 `specs/api/openapi.yml` 的 GET /user 明确列出 401，Unauthorized 引用 GenericErrorModel：errors 对象的值为字符串数组。其 `errors.token=["is missing"]` 是缺少 Token 的示例，不意味着所有异常 Token 都必须叫 is missing。

复现未修复版本：

```bash
.venv-test/bin/python -m pytest 'tests/api/test_users.py::test_protected_user[invalid-token]' -v --backend-variant=baseline --evidence-dir=.runtime/bug001-before
```

预期：401、JSON 错误结构；实际：500、text/plain（DEBUG 下的异常栈）。阶段 2.5 的独立复现为 1 failed，见 baseline-repro.txt。原有测试断言未放宽，原文件未修改。

## 4. 异常栈与具体根因

关键实测栈（完整版本见 before/backend.log 和 baseline-repro/backend.log）：

```text
ninja/operation.py, line 212, in _run_authentication
    result = callback(request)
helpers/jwt_utils.py, line 64, in __call__
    auth_details = self.authenticate(request, token)
helpers/jwt_utils.py, line 82, in authenticate
    raise APIError("invalid_token", 401) from None
jwt_ninja.errors.APIError: ('invalid_token', 401)
GET /api/user HTTP/1.1 500
```

调用链：

1. `jwt_ninja.cryptography.decode_jwt` 调用 PyJWT 验签与解析；格式/签名异常被转换为 JWTInvalidTokenError，过期转换为 JWTExpiredError。
2. RealWorld 的 `TokenAuth.authenticate` 再分别转换成 `APIError('invalid_token', 401)` 或 `APIError('expired_token', 401)`。
3. 受保护接口的 `TokenAuth.__call__` 将 APIError 继续抛出；可选认证接口的匿名回退分支不在本次修改范围。
4. Django Ninja `_run_authentication` 捕获异常并交给当前 `NinjaAPI.on_exception`。它按异常类型的 MRO 查找已注册处理器，不会自动读取任意异常的 http_status_code 属性。
5. `jwt_ninja.errors.APIError` 直接继承 Exception，并非 Ninja 的 HttpError。RealWorld 主 API 没有注册 APIError 处理器，于是匹配默认 Exception 处理器；DEBUG=True 时返回 500 text/plain。

对照：缺少 Token 时回调返回 None，Ninja 生成 AuthenticationError；它是 HttpError 子类，能匹配现有处理器，因此得到 401。这解释了“缺少 Token 正常、非法 Token 反而 500”，不是网络随机失败。

归因：当前固定版本组合下，**RealWorld 主 API 与 jwt_ninja 异常类型之间的集成缺陷**。请求头构造正确，不是测试代码误报；数据库迁移、注册、合法认证均正常，独立无账号也复现，不是数据库初始化或测试顺序问题。DEBUG 决定异常正文形式，但遗漏异常处理器才是返回错误状态的原因。未验证生产配置、其他依赖版本，因此不外推它们的具体响应。

## 5. 最小修复及边界

唯一业务文件变更是 `config/urls.py`，补丁增加 1 行 import 和 1 个处理器（共 6 行新增，包含空行）：

```diff
+from jwt_ninja.errors import APIError
+
+@api.exception_handler(APIError)
+def jwt_api_error_handler(request: HttpRequest, exc: APIError) -> HttpResponse:
+    return api.create_response(request, {"errors": {"token": [exc.error_code]}}, status=exc.http_status_code)
```

精确差异以 `patches/BUG-001.patch` 为准。这个处理器只匹配 APIError，保留其中的状态码和错误码，不重构 TokenAuth，不绕过签名/过期校验，不修改密码、会话或权限逻辑，也不把 Exception 统一改成 401。

响应选择：缺少/不识别认证头仍走原有 `{"errors":{"token":["is missing"]}}`；无效 JWT、签名错误经新增处理器返回 invalid_token；过期返回 expired_token。后二者是本地修复明确采用的消息约定，符合规范通用错误结构，不声称规范强制要求这些精确文字。

额外的 `scripts/probe_bug001_dispatch.py` 是**异常分发故障注入探针**，直接调用真实 api.on_exception，不算 HTTP 业务用例：APIError 401 → 401、APIError 400 → 400、普通 RuntimeError → 500，结果保存在 dispatch-probe.json。它证明没有全局掩盖服务端异常；其中 RuntimeError 是人为注入，不是另一个产品 Bug。

## 6. 认证边界验证

新增 7 条独立参数实例；每条先使用真实注册得到的 Token 成功查询身份，建立有效用户/会话的对照。

| 场景 | 构造 | 未修复 HTTP | 修复后 HTTP / 消息 |
|---|---|---:|---|
| 缺少 Token | 不发 Authorization | 401 | 401 / is missing |
| 无效 Token | 三段 JWT，签名无效 | 500 | 401 / invalid_token |
| 错误认证头格式 | Basic 前缀 | 401 | 401 / is missing |
| 错误 JWT 格式 | Token only.two | 500 | 401 / invalid_token |
| 篡改签名 | 解码真实签名，将第一个字节异或 1，再编码 | 500 | 401 / invalid_token |
| 已过期 Token | 保留用户/会话，只改 exp 为过去 60 秒，用本地测试密钥重新签名 | 500 | 401 / expired_token |
| 合法 Token | 真实注册 Token | 200 | 200 / 身份匹配 |

过期构造不是简单改 payload（那会造成签名错误）。辅助进程先验证原始签名，再用后端已安装的 PyJWT 和测试配置签名，最后确认 PyJWT 抛 ExpiredSignatureError。没有 sleep 等待、没有关掉验签、没有新增发 Token 的业务接口，不输出密钥或 Token 到报告。此操作仅用于自己的隔离测试环境。

## 7. 实际回归结果

| 运行 | 通过 | 失败 | 跳过/错误 | JUnit 秒数 |
|---|---:|---:|---:|---:|
| 未修复全量 27 条 | 22 | 5 | 0 / 0 | 5.503 |
| 未修复 BUG-001 独立复现 | 0 | 1 | 0 / 0 | 1.123 |
| 修复后新增认证边界 | 7 | 0 | 0 / 0 | 2.328 |
| 修复后原有 20 条 | 20 | 0 | 0 / 0 | 3.912 |
| 修复后全量第 1 次 | 27 | 0 | 0 / 0 | 5.107 |
| 修复后全量第 2 次 | 27 | 0 | 0 / 0 | 5.139 |
| 修复后反序全量 | 27 | 0 | 0 / 0 | 5.248 |

未修复的 5 条失败属于同一根因的不同输入表现，不统计为 5 个不同 Bug。原有20条中的注册、登录、CRUD、401、403均回归通过。不存在 skip/xfail/放宽断言；原有 tests/api/test_users.py 和 test_articles.py 未改。

每轮文章清理至 0，进程停止，临时数据库和源码目录实际确认不存在。完整命令与退出码见 commands.json，逐条结果和耗时见 summary.json、各轮 results.xml，原始终端输出及后端日志同时保留。时间为整轮执行，不是性能测试指标。

## 8. 严重程度与剩余问题

建议严重程度中等、优先级 P2（练习项目分级）：未授权输入本应被正常拒绝，却触发 500，影响客户端处理、错误率监控和接口可靠性；DEBUG 下还暴露内部堆栈。没有证据证明鉴权绕过、合法数据泄露或服务不可用，不夸大为严重安全漏洞。

主 API 的处理器也会覆盖同一 API 实例下 /auth 路由抛出的 APIError。保留原状态码并做了 400 分发探针，但本阶段没有完整回归 /auth 刷新/撤销等扩展接口。过期会话、停用用户、可选认证接口、并发和 PostgreSQL 均未完整验证。

原始上游仓库和手动 backend.sh 服务仍是未修复版本；只有 pytest 的 fixed 变体自动应用补丁。部署或向上游提交需另行安排。当前完成的是授权范围内的本地可控修复闭环。

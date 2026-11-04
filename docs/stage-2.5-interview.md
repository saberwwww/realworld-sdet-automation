# 阶段 2.5：把一个真实 Bug 讲清楚

## 为什么无效 Token 返回 500 属于异常？

客户端可能过期登录、复制错 Token 或发送垃圾字符串。接口应该把这种可预期输入当成认证失败，而不是程序崩溃。本项目 GET /api/user 的规范明确列出 401；测试却得到 500，所以是接口契约问题。

500 本身只能证明请求失败，不能直接证明原因。我们进一步看了错误栈、异常类型和 Django Ninja 的处理器匹配机制，才确认根因。

## 401、403、500 有什么区别？

| 状态 | 通俗解释 | 本项目例子 |
|---|---|---|
| 401 | 没有通过身份认证 | 没有 Token、签名错误、Token 过期 |
| 403 | 身份已确定，但没有操作权限 | 用户 B 修改或删除用户 A 的文章 |
| 500 | 服务端发生未正常处理的错误 | APIError 没有匹配处理器而进入默认异常处理 |

不要把所有错误都变成 401：数据库故障或程序 RuntimeError 仍应按服务端异常处理。本次补丁只处理 APIError，并采用它自带的状态码。独立探针也实测 400 保持 400、普通 RuntimeError 保持 500。

## 为什么这是接口自动化测试发现的问题？

`tests/api/test_users.py` 通过 requests 向真实 Django 服务发 HTTP 请求，使用规范的 Authorization: Token 前缀，检查响应状态和错误对象；不是只测试一个 Python 函数，也没有 mock 后端。

只测注册、登录成功容易漏掉认证异常。参数化的 missing-token 通过、invalid-token 失败，让我们看到不同输入走了不同服务端分支。自动化还能固定输入和断言，反复复现，并在修复后检查它是否回来。

阶段 2 首次 19/20 通过；阶段 2.5 新增 7 条后，修复前 22/27 通过，5 条失败都来自同一个根因。不能把它说成发现 5 个不同 Bug。

## 怎样通过日志和代码定位根因？

先看 pytest 输出：GET /api/user，期望 401，实际 500，text/plain。再看同一轮 backend.log：TokenAuth.authenticate 抛出 APIError('invalid_token', 401)。

关键追问是：“异常里写着 401，为什么 HTTP 仍是 500？”

因为异常对象的属性不会自动变成响应。Django Ninja 捕获异常后按类型寻找处理器，而 APIError 直接继承 Exception，不继承已注册的 HttpError。RealWorld 主 API 缺少 APIError 处理器，因此用了默认 Exception 处理器，返回 500。

无 Token 时回调返回 None，Ninja 生成的是 AuthenticationError，它属于 HttpError，所以原先能正确返回 401。这个对照把根因讲完整了。

具体看 `patches/BUG-001.patch`：只给主 API 注册一个 APIError 处理器，采用 exc.http_status_code，返回符合规范的 errors 字符串数组。没有修改 JWT 解码、签名校验或权限判断。

## 怎样证明修复没有破坏其他接口？

不是只让原来失败的一条变绿：

- 在原始固定 commit 的临时副本上复现失败，保留日志和 JUnit。
- 新增缺少、无效、错误格式、篡改签名、过期及合法 Token 等 7 条边界实例，修复后全部通过。
- 原有 20 条独立运行全部通过，包含注册、登录、文章 CRUD、未登录和非所有者访问。
- 全量 27 条连续两次、再反序执行，均全部通过；没有跳过或修改原来预期。
- 每轮检查文章清理和数据库销毁，减少残留数据导致的假通过。

这些证据说明“在当前已覆盖范围没有观察到回归”，不能保证所有未覆盖功能永远无 Bug。/auth 刷新/撤销、生产模式和 PostgreSQL 未完整回归，面试时应主动说清范围。

## 如何可靠构造过期和篡改 Token？

`test_auth_boundaries.py` 的 tamper_signature 拆成三段，解码签名字节，真正改变一个字节后再编码；保留 header 和 payload。这样保证是签名改变，而不是 Base64 最后一位填充等价。

过期 Token 用 `tests/support/mint_expired.py`：先验原 Token 的签名，只改 exp 为过去 60 秒，用隔离测试环境的本地密钥重新签名，再验证库确实抛 ExpiredSignatureError。仅修改 payload 不重签会变成“签名错误测试”，不是“过期测试”。整个过程不等待时钟、不关验签、不把密钥或 Token 打进日志。

错误消息也要区别：缺少 Token 沿用 is missing，解析/签名失败用 invalid_token，过期用 expired_token。精确消息是本地补丁明确的实现约定；通用 JSON errors 结构和 HTTP 401 来自 API 契约。

## 面试时的一分钟讲法

> 我基于开源 RealWorld 做了独立的 pytest 加 requests 接口测试。最初 20 条里有一条失败：带无效 Token 查询当前用户，预期 401，实际 500。确认请求头符合规范后，我在独立数据库里复现，并沿日志追到 TokenAuth 抛出的 APIError。它虽然携带 401，但不继承 Django Ninja 的 HttpError，主 API 又没注册对应处理器，所以落入默认 500 处理。我用独立补丁只增加这个异常类型的响应转换，没有修改验签或权限逻辑。随后补了签名篡改、过期和合法 Token 等边界测试，原有 20 条全部通过，27 条全量连续两次和反序也通过。原始源码和失败证据都保留，目前只完成本地修复，未向上游提交。

准备追问：你应能自己写出带 Token 的 requests 请求、一个状态/JSON 断言、参数化用例，以及说明 fixture 如何隔离和清理。更复杂的 Token 签名工具不必背代码，但必须解释为什么“过期”与“签名错误”是不同测试。

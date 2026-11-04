# UI 测试设计（阶段 3）

对象：固定来源的 RealWorld Vue3 前端、Django Ninja + BUG-001 临时补丁后端。Chromium、1280×900、英文界面；每轮临时 SQLite，每条独立 browser context。8 条独立实例，未使用或复制上游 JavaScript Playwright 测试。

## 场景与判定依据

| 用例 | 前置条件（API/环境） | 实际 UI 操作 | 预期结果与断言 |
|---|---|---|---|
| test_login_success | API 注册本条唯一用户；浏览器无认证状态 | 输入邮箱密码，点击 Sign in，刷新 | 登录请求到本地 API 且200；回到首页，导航显示本用户和 New Article，Sign in 消失；刷新后仍成立 |
| test_login_wrong_password | API 注册用户 | 输入正确邮箱、错误密码并提交 | 实际401；页面显示 credentials invalid；仍在/login，无 New Article |
| test_logout | API 注册，浏览器真实登录 | Settings → logout；再访问/settings | 回首页，出现 Sign in、用户名消失；再次访问设置页重定向/login |
| test_publish_article | API 注册，浏览器登录；未通过API创建文章 | New Article → 输入标题/摘要/正文 → Publish | 浏览器POST返回201，进入文章详情，标题正文可见；刷新仍可见 |
| test_edit_article | API 注册并创建本用户文章；浏览器登录 | 打开文章 → Edit Article → 修改正文 → Publish → 刷新 | 编辑器先显示原正文；PUT为200；修改后正文可见，刷新仍生效，旧正文不可见 |
| test_delete_article | API 创建本用户文章；浏览器登录 | 详情页 Delete Article → 首页 → 刷新 | 浏览器DELETE为204，回首页且空列表，无原文章标题；额外API查询404作为辅助验证 |
| test_guest_editor_redirect | 新context，未登录 | 直接访问/editor | 重定向/login，显示Sign in标题，不显示Publish Article |
| test_publish_empty_title | API 注册，浏览器登录 | 输入空标题、合法摘要正文，点击Publish | 浏览器POST为422；title / can't be blank 错误显示，仍在/editor，正文未丢失，按钮恢复可操作 |

API 准备只用于快速建立独立账号和编辑/删除的文章前置条件；登录、退出、发布、编辑和删除动作均由真实浏览器执行。不使用 storage_state 或直接注入 Token 绕过登录。不存在请求 fulfill/mock 业务成功响应。

## 依据

- `src/views/Login.vue`、`src/store/auth.js`：登录表单、错误格式及登录状态。
- `src/components/TheHeader.vue`：认证后用户名、New Article、Settings 导航。
- `src/views/Settings.vue`：退出清理认证状态并导航首页。
- `src/views/ArticleEdit.vue`、`src/components/ArticleActions.vue`：发布/编辑/删除行为。
- `src/main.js` 和 `src/router/index.js`：requiresAuth 对/editor、/settings的保护。
- RealWorld固定OpenAPI及已验证的后端：201、200、204、401、422等状态。

先阅读真实组件，再通过首条真实登录和首次全量执行核对页面行为。页面没有给输入设置label，因此用稳定placeholder；导航/按钮/标题优先role+name。文章操作上下重复出现，明确限定顶部banner，不依赖任意first或长XPath。

## 数据、顺序与范围

每条用户UUID唯一；UI fixture只列出、校验并删除该用户名下文章。原有API fixture不变。账号无法通过业务API删除，在整轮结束时随临时数据库销毁。没有全库删除SQL，也不访问演示库或公共服务。删除后空列表断言建立在该隔离环境中其余文章已正确清理的前提上；若其他用例泄漏文章会真实失败。

每条运行前检查空cookie和localStorage中无jwtToken；官方插件关闭每条context；会话结束检查context数为0并关闭browser。独立上下文避免认证残留；UUID和清理避免服务端数据冲突。两种隔离解决不同问题，不能只做其中一种。

界面时间同步采用Playwright action自动等待、expect轮询和expect_response绑定具体请求；UI代码无time.sleep。服务启动器的0.1秒轮询只用于探测本地端口启动，不用于掩盖页面异步。

网络策略只允许本轮前端、后端两个回环origin：任何外部fetch/xhr会阻断并使审计失败；外部字体/CSS等静态资源同样阻断并记录，避免外部可用性影响业务测试。本地页面样式与业务代码正常运行；不验证外部字体或像素一致性。

## 诊断演示（不计入8条）

`tests/ui/diagnostics_demo.py` 显式执行：浏览器登录、发布文章、先验证真实标题，再故意期待 INTENTIONAL WRONG TITLE。预期它失败，并保留截图、Trace、断言栈、控制台、真实网络请求；文章仍由fixture清理。它是错误断言注入，不是产品Bug，也不作为正式套件通过率分母。

## 不在本阶段范围

不包含Firefox/WebKit、移动端、文件上传、邮件、富文本复杂输入、验证码、视觉基线、可访问性完整审计、并发UI、CI、性能和数据库字段一致性测试。API注册不等价于UI注册覆盖；本套件没有宣称覆盖UI注册。未完整测试删除后直接访问失效文章URL的错误页展示。

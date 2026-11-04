# 阶段 3：结合真实代码讲 UI 自动化

## 1. UI 自动化与接口自动化有什么区别？

接口测试直接用requests发HTTP，验证状态码、JSON和业务规则，较快且定位范围小。UI测试让浏览器点击真实页面，覆盖输入→Vue事件→请求→后端→页面变化，能发现页面路由、错误提示、状态展示等接口测试看不到的问题，但涉及更多环节。

本项目并列保留27条接口测试和8条UI测试。编辑/删除UI测试通过API准备文章，是为了稳定建立前提；真正编辑/删除仍由浏览器按钮触发。不要把API准备说成UI验证。

## 2. Playwright怎样定位元素？

`LoginPage.submit` 用 `get_by_placeholder("Email", exact=True)` 找邮箱输入框，用 `get_by_role("button", name="Sign in", exact=True)` 找提交按钮。页面实际没有label，所以不能假装用get_by_label能工作。

role是元素的语义角色，name是可访问名称。链接和按钮都叫Sign in时，role可以区分；exact避免误匹配包含相同文字的其他元素。先限制到navigation，再查找用户名，能避免正文里同名文字干扰。

文章顶部和底部都有编辑/删除按钮，`ArticlePage` 先限定 `.article-page .banner`，再按role找按钮。短CSS只用于没有合适语义的容器和错误列表，没有长XPath，也不靠nth(0)碰运气。

## 3. POM是什么，为什么用？

Page Object Model把一个页面的定位和常见操作放进一个Python类。这里LoginPage负责输入和提交；HomePage负责登录后导航检查；EditorPage负责填表和发布；ArticlePage负责查看内容、编辑和删除。

如果邮箱placeholder改了，只改LoginPage，不用改每条用例。测试函数保留业务意图，比如“修改正文并刷新确认”，而不是几十行重复定位。没有给每个按钮创建类，也没有通用关键字平台。POM是降低重复的手段，不是封装层数越多越专业。

## 4. fixture怎样管理浏览器和用户？

官方pytest-playwright提供browser/context/page。`tests/ui/conftest.py` 通过插件扩展点配置viewport和base_url，并复用前面阶段的临时后端fixture。

`ui_user`先调用原有owner fixture，用API注册本条账号；yield将账号交给测试，之后只清理该账号文章。`logged_in`用LoginPage真正输入并登录。`prepared_article`只给编辑/删除测试做API前置准备。

`frontend_url`在整个session启动一个Vite进程，并通过环境变量VITE_API_URL连接本轮后端；yield结束停止进程。账号最后随本轮临时数据库销毁。断言失败不等于跳过正常teardown。

本机最终固定 `--browser-channel=chromium` 使用完整Chromium的新无头模式。默认Headless Shell曾在click等待稳定阶段超时，保留其失败证据；不是通过force或sleep绕过。详情见阶段报告，底层兼容性原因仍未完全确定。

## 5. browser、context、page分别是什么？

- browser：本轮启动的Chromium实例，多条测试可复用，避免反复启动成本。
- context：独立浏览器会话，有隔离的cookie和localStorage；每条测试一个。
- page：context中的一个标签页，负责导航、定位和点击。

复用browser不意味着共享登录态，因为登录态存在隔离的context里。本项目没有直接new_context绕开官方fixture，因此截图和Trace命令行选项能生效。

## 6. 如何避免UI测试互相影响？

浏览器端，每条新context，首次进入/login时检查cookie为空且localStorage无jwtToken；不使用共享storage_state。服务端，每条UUID账号、每轮独立数据库，文章精确按作者清理。还要区分“页面关了”和“数据删除了”：关闭context不会删除后端文章。

本阶段实际执行连续两次、反序、API+UI混合套件；审计context创建/关闭数量和进程残留。它能发现已观察到的顺序污染，但不等于验证了全部排列和并发。

## 7. 为什么不推荐time.sleep？

sleep(2)只代表等了两秒，不代表按钮可点或请求完成。机器快时浪费时间，机器慢时仍失败。

本项目click会等待元素可操作；expect(locator).to_be_visible会在超时内重试；expect_response先监听对应请求，再点击，避免错过很快返回的响应。网络返回成功后仍要用expect确认DOM更新，因为收到HTTP响应不等于Vue已完成渲染。没有用networkidle等待第三方资源或用固定延迟碰运气。

服务启动器的短轮询是在探测进程是否ready，与UI测试中sleep等待页面不同。

## 8. 登录成功怎么断言？

不能只看click没有报错，也不能只看登录API200。`test_login_success`同时检查：响应URL是本轮本地/api/users/login，状态200；页面回首页；导航显示本账号用户名与New Article；Sign in消失；刷新后这些状态仍成立。

错误密码用例另查401和页面credentials invalid，仍留在登录页且没有New Article。这样同时覆盖成功与失败的可观察行为。

## 9. 怎样用截图、Trace和网络定位失败？

先看pytest的node id、POM/断言位置及Playwright调用日志；再看失败截图，确认当时页面；用Trace回放动作和DOM快照，查看请求是否发出、地址是否正确、返回状态是否异常。

本项目通过官方插件默认开启 `--screenshot=only-on-failure --tracing=retain-on-failure`。每条额外保存脱敏的网络元信息（方法/URL/状态）、console/pageerror和失败请求，不输出Authorization或完整响应体。

真实诊断演示先发布文章，再故意期待不存在的标题。截图应显示真实文章，Trace应有发布请求201和失败的expect；说明问题是主动注入的错误预期，不是产品发布失败。清理记录仍应显示文章归零。

分类思路：

- 后端与规范矛盾、稳定可复现：可能是产品Bug，继续看日志和最小复现。
- 页面正常，但定位歧义/错误标题：测试代码或主动注入问题。
- 浏览器未安装、端口启动失败、公共API配置错误：先查环境和配置。
- 401负向请求引起的浏览器资源报错：结合预期场景判断，不能把所有console error都算Bug。

本工程阻断外部静态资源，相关ERR_FAILED是网络隔离策略的结果，记录在blocked_external_assets里；与本地业务API失败区别对待。Trace可能包含测试账号密码和临时Token，只应本地查看，不能直接公开分享原始压缩包。

## 10. 哪段代码应该能脱离AI写出来？

至少能独立写出“打开登录页→定位输入→fill→click→expect用户名”的直线代码，然后解释fixture如何提供page和用户。再练习把重复操作提成LoginPage方法。重点掌握Python函数参数、字典取值、class/self、with上下文管理、assert与expect的区别，不必背浏览器驱动内部实现。

本项目核心代码在 `tests/ui/pages/auth.py` 的submit和 `tests/ui/test_business.py` 的test_login_success。expect_response返回的是真实网络响应；expect是自动重试的页面断言，普通assert不会自动等待DOM。

## 不依赖AI的小练习（30分钟）

先关闭AI补全，自己创建 `tests/ui/exercise_login.py`，文件名不以test_开头，避免未完成练习进入默认正式套件。写函数 `test_exercise_login(page, frontend_url, ui_user)`，不要调用现成POM或logged_in fixture。

只允许查Playwright官方文档，完成以下步骤：

1. 用page.goto打开真实frontend_url + /login。
2. 找到Email、Password输入框；从ui_user字典取值输入。
3. 找到role为button、名称为Sign in的按钮并点击。
4. 用expect等待回到首页，导航显示ui_user["username"]，Sign in链接消失。
5. 刷新页面，重复登录状态断言。
6. 自己把密码改错，观察失败截图/Trace，再恢复正确密码。

运行自己的文件：

```bash
.venv-test/bin/python -m pytest tests/ui/exercise_login.py -v --evidence-dir=.runtime/exercise-login --output=output/playwright/exercise-login
```

验收：不抄POM、不sleep、不直接写入localStorage、不mock接口；能解释为什么按钮点击成功不是登录成功。exercise_login.py是留给你的练习，本次没有创建或执行，不能算已通过用例。

参考：[官方pytest插件](https://playwright.dev/python/docs/test-runners)、[Trace Viewer](https://playwright.dev/python/docs/trace-viewer-intro)。

# 项目面试深挖指南

## 一分钟介绍

“我基于开源 RealWorld 的 Vue3 前端和 Django Ninja 后端，独立开发了 Python 自动化测试工程。正式有27条接口和8条UI测试，其中5条结合SQLite检查持久化结果。fixture会创建临时数据库和独立用户，UI每次使用新的浏览器context，结束后清理文章、进程和数据库。我通过无效Token用例发现500，结合服务端堆栈定位到JWT库异常没有被主API处理，在临时源码副本应用最小补丁，再对认证边界和全部业务回归。最后编写GitHub Actions配置，复用本地启动器并保留JUnit、截图和Trace。目前本地验证通过，远程CI尚未运行。”

## 你具体开发了什么？

讲 tests/、scripts/、patches/ 和 .github/workflows/；开源前后端是被测对象，不能声称自己开发业务系统。UI测试是Python实现，不是复制上游JS测试。先打开 tests/api/test_articles.py 与 tests/ui/test_business.py 讲一个完整动作，再解释公共fixture。

## 为什么不只断言200？

状态码只说明处理结果的一部分。创建应有正确作者、字段和唯一标识；SQL再证明真正持久化。更新应保持同一id、改变目标字段、没有重复行；越权失败应保留原记录。代码在 tests/support/assertions.py 与 database.py；API/UI/SQL从不同观察点相互印证，但数据库一致不等价于业务语义完全正确。

## fixture如何处理失败、依赖和作用域？

session环境复用服务以控制成本；function用户、API会话和context避免状态共享。yield前准备，后面清理；pytest断言失败仍会执行已完成setup的fixture teardown。文章工厂先登记作者，清理按作者查询最新slug，防止改标题后旧slug无法删除。若setup在yield前异常，要靠对应contextmanager的finally兜底，不能笼统说所有yield代码一定执行。

## SQL与隔离为什么安全？

server.py只传递本轮临时数据库路径。database.py以mode=ro连接，用WHERE参数绑定，JOIN文章作者；用户输入不是表名。业务动作仍通过API/UI，SQL只是观察。用户无删除接口，结束销毁本次临时库；不对任意数据库执行全库DELETE。

## BUG-001根因是什么？

非法JWT在JWT库中被转换为APIError，但主NinjaAPI没有对应异常处理器，导致异常落入500路径。测试头符合Token scheme，合法Token对照通过；堆栈指向异常分发，故不是只看500就下结论。补丁只注册APIError处理器，保留异常定义的状态和错误码，不捕获所有Exception，不弱化认证断言。401是认证失败，403是已识别主体权限不足，500是服务端非预期异常；以具体接口实现与契约对照。

baseline会真实失败；fixed在每轮临时源码应用同一patch。上游checkout始终不改，不把本地修复说成上游已合并。历史详情见 bugs/BUG-001-invalid-token-500.md。

## UI为什么容易不稳定，如何定位？

browser是浏览器实例，context是独立会话，page是标签页。语义定位和expect自动等待代替固定sleep；登录同时验证真实请求与用户名/导航变化。失败先看pytest具体断言，再看截图和Trace的action/DOM/network。Headless Shell的点击超时是当前环境实际问题，完整Chromium稳定，所以固定channel而不是降低断言。不能由macOS结果推断Linux完全相同。

## CI到底验证到了什么？

工作流固定Ubuntu、Python、Node和action SHA；bootstrap安装，fixture启动服务及迁移，run_tests输出JUnit与汇总，always上传证据。bash的pipefail让安装命令失败不被tee吞掉。正式job不使用continue-on-error。展示本地实际结果，并明确GitHub托管runner尚未执行；workflow语法检查不是远程绿灯。

固定版本不代表完全可复现：Python锁目前没有全部分发哈希，apt系统包会变，外网下载可能失败，Linux尚待实跑；固定commit与npm integrity减少漂移但不是供应链完整证明。

## 现场应能独立写出的代码

1. requests.Session发POST JSON、携带Authorization: Token、timeout，断言状态/字段。
2. pytest fixture中yield和finally资源清理；参数化无效输入及有意义的id。
3. 使用sqlite3、参数绑定、fetchone和连接关闭，解释SELECT/WHERE/JOIN。
4. Playwright定位登录输入、点击、expect登录后用户名；解释自动等待和context。
5. subprocess.run(check=True)、Popen及poll/wait；区分进程退出和HTTP真正就绪。
6. 阅读JUnit并计算通过/失败/错误/跳过，不能用日志里某行“passed”掩盖退出码。

练习：不借助AI，在现有框架添加一个临时教学文件，使用owner和api创建文章，使用db按id查询title/content并断言，再在finally通过API删除。先讲清前置数据、业务动作、两层断言和失败清理，再编码；不把教学文件算作已验证正式新增用例。

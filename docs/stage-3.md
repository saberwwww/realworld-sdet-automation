# 阶段3：Playwright Python UI 自动化

验证日期：2026-11-03（Asia/Shanghai）。已实现8条UI业务测试，固定完整Chromium新无头模式后，连续两次和反序均通过；27条API回归通过，35条API+UI混合执行通过。保留了不通过的Headless Shell实验和主动诊断注入记录，没有把它们删除或改成通过。

场景前提、步骤和依据见 [UI设计](test-design-ui.md)；10个面试问题及独立登录练习见 [面试文档](stage-3-interview.md)。

## 代码归属与配置

**被测开源代码**：upstream/frontend 的Vue3组件、路由、store与样式；upstream/backend的Django Ninja业务；来源和固定commit见config/upstream.json。没有修改前端业务源码，没有复制/执行上游JS Playwright用例作为个人成果。

**既有本地补丁**：继续由隔离后端启动器导出原始commit，fixed变体仅应用patches/BUG-001.patch。原始克隆和baseline变体不变。旧阶段证据及provenance中的文件SHA已复核未改变。

**本次新增Python测试代码**：

```text
tests/ui/
  conftest.py                 前端生命周期、插件配置、用户准备/文章清理、网络/认证/关闭审计
  pages/auth.py               LoginPage、HomePage
  pages/articles.py           EditorPage、ArticlePage
  test_business.py            8条业务UI测试
  diagnostics_demo.py         显式执行的错误断言演示，默认不收集
tests/support/frontend.py    原始Vite启动器，注入临时后端URL
```

修改pytest.ini：默认收集tests/api和tests/ui，共35条；使用官方插件的截图/Trace选项，固定browser-channel=chromium。新增config/ui-test.lock.txt，原API锁文件不改；README更新安装和执行方式。tests/ui包文件只是Python导入入口，没有通用测试平台。

## 环境核验与首条真实验证

已阅读README、阶段2.5报告、原fixture/后端隔离实现，以及真实前端Login、Settings、ArticleEdit、Article、Header、Actions、路由和认证store。

实际安装：pytest-playwright 0.10.0、Playwright 1.64.1；沿用Python 3.13.7、pytest 9.2.0。pip check通过，插件声明pytest>=7且<10，与当前版本一致，元数据见python-environment.json。Chromium版本156.0.8078.4，浏览器下载在工程.runtime/pw-browsers，不修改用户Chrome安装。

```bash
.venv-test/bin/python -m pip install -c config/test.lock.txt pytest-playwright
PLAYWRIGHT_BROWSERS_PATH="$PWD/.runtime/pw-browsers" .venv-test/bin/python -m playwright install chromium
.venv-test/bin/python -m pip check
```

先只写1条登录测试并真实运行，成功后才扩展其余用例。首条使用完整Chromium通道，1 passed in 9.06s；截图、Trace和本地网络记录保存在smoke目录。初次有插件base_url绑定方法在pytest9.2下的弃用提示；通过官方fixture覆盖入口定义普通session base_url，同时提供本地地址，后续无该提示，未屏蔽警告或升级依赖。

前端源码默认URL是公共api.realworld.show，因此启动器显式设置VITE_API_URL为当前临时后端。测试还断言实际登录response.url精确等于该地址的/users/login。每条保存fetch/xhr实际响应方法、URL、状态；最终运行审计确认所有记录均为本轮本地API地址。不是只检查环境变量。

context网络守卫只允许本轮本地前后端origin：外部API尝试会被阻断且报错；外部字体和图标CSS也被阻断并记录。无业务请求mock。字体/图标CSS阻断带来的ERR_FAILED不是新的产品Bug；页面使用本地主题且可以正常操作。

## 浏览器模式问题：真实失败与处理

第一条及首次8条全量使用 `--browser-channel chromium`，均通过。随后省略channel使用独立Headless Shell时，登录按钮点击等待visible/enabled/stable超时，后端日志无对应登录请求；初始8条得到1通过、2失败、5个fixture错误。非登录的访客重定向正常。同样输入和页面在完整Chromium通道通过。

这是当前机器/浏览器模式的兼容性现象，底层原因尚未完全定位，不能据此认定RealWorld业务Bug。没有加force click、sleep、重试或放宽业务断言。采用官方支持的完整Chromium新无头模式固定本地运行配置，重新验证稳定性。官方说明这两种headless模式存在实现差异：[浏览器模式文档](https://playwright.dev/python/docs/browsers#chromium-new-headless-mode)。

尝试停止旧超时轮次时，一次进程检查因自动审批服务额度限制未执行；继续后确认旧批次已自行结束且无残留进程。旧轮次未隐藏，仍见commands.json和原日志。最终验证脚本增加逐轮退出码检查，出现非预期失败便停止后续批次。

| 早期/失败实验 | 通过 | 失败 | 错误 | JUnit秒数 |
|---|---:|---:|---:|---:|
| smoke：完整Chromium，首条 | 1 | 0 | 0 | 9.067 |
| initial：完整Chromium，首次全量 | 8 | 0 | 0 | 12.452 |
| ui-run-1：Headless Shell | 1 | 2 | 5 | 259.797 |
| ui-run-2：Headless Shell | 1 | 2 | 5 | 256.494 |
| ui-reverse：Headless Shell | 1 | 2 | 5 | 256.370 |
| diagnostic：Headless Shell，未到注入断言 | 0 | 0 | 1 | 37.467 |
| combined：Headless Shell混合轮 | 28 | 2 | 5 | 260.055 |

“错误”指fixture准备期间异常，不能误算成业务断言失败。早期diagnostic卡在登录准备，不能宣称验证成功；诊断机制的成功证据使用后面的chromium-diagnostic。

## 最终真实结果

所有正式最终轮次无skip/xfail。诊断注入单独执行，不混入业务通过率。

| 轮次 | 收集数 | 通过 | 失败 | 错误 | JUnit秒数 |
|---|---:|---:|---:|---:|---:|
| chromium-run-1 | 8 | 8 | 0 | 0 | 12.212 |
| chromium-run-2 | 8 | 8 | 0 | 0 | 11.435 |
| chromium-reverse | 8 | 8 | 0 | 0 | 11.234 |
| api-regression | 27 | 27 | 0 | 0 | 4.949 |
| chromium-combined | 35 | 35 | 0 | 0 | 15.152 |
| chromium-diagnostic（主动注入） | 1 | 0 | 1 | 0 | 4.205 |

耗时包含fixture和服务准备，不作为性能指标。最终完整Chromium各轮参数和退出码见chromium-commands.json；API独立回归参数在commands.json；summary.json由真实JUnit解析，保留全部早期和最终结果。

实际执行的最终命令（当前pytest.ini已固定Chromium通道）：

```bash
.venv-test/bin/python -m pytest tests/ui -v --evidence-dir=evidence/stage-3/chromium-run-1 --junitxml=evidence/stage-3/chromium-run-1/results.xml --output=output/playwright/stage-3-chromium-run-1
.venv-test/bin/python -m pytest tests/ui -v --evidence-dir=evidence/stage-3/chromium-run-2 --junitxml=evidence/stage-3/chromium-run-2/results.xml --output=output/playwright/stage-3-chromium-run-2
.venv-test/bin/python -m pytest tests/ui --reverse-order -v --evidence-dir=evidence/stage-3/chromium-reverse --junitxml=evidence/stage-3/chromium-reverse/results.xml --output=output/playwright/stage-3-chromium-reverse
.venv-test/bin/python -m pytest tests/ui/diagnostics_demo.py -v --evidence-dir=evidence/stage-3/chromium-diagnostic --junitxml=evidence/stage-3/chromium-diagnostic/results.xml --output=output/playwright/stage-3-chromium-diagnostic
.venv-test/bin/python -m pytest tests/api -v --browser chromium --evidence-dir=evidence/stage-3/api-regression --junitxml=evidence/stage-3/api-regression/results.xml --output=output/playwright/stage-3-api-regression
.venv-test/bin/python -m pytest -v --evidence-dir=evidence/stage-3/chromium-combined --junitxml=evidence/stage-3/chromium-combined/results.xml --output=output/playwright/stage-3-chromium-combined
```

## 失败诊断证据

故障注入先真实登录并发布 `Diagnostic article - real browser`，验证它显示成功，然后故意查找不存在的 `INTENTIONAL WRONG TITLE`。pytest准确指出diagnostics_demo.py第13行及定位器，附带真实ARIA快照。分类为主动注入的测试错误，不是产品Bug。

已生成并目视检查截图，页面显示真实文章标题和正文。已检查Trace ZIP完整性，以及其中动作记录、DOM快照、连续画面和真实POST /api/articles 201网络记录，见trace-validation.json。没有将程序检查描述为手工操作Trace Viewer GUI；可用下面命令本地交互查看动作/DOM/网络。

- 截图：`output/playwright/stage-3-chromium-diagnostic/tests-ui-diagnostics-demo-py-test-injected-wrong-title-chromium/test-failed-1.png`
- Trace：同目录`trace.zip`
- 断言日志：`evidence/stage-3/chromium-diagnostic.txt`
- 请求/控制台：`evidence/stage-3/chromium-diagnostic/browser/`
- 文章清理：`evidence/stage-3/chromium-diagnostic/ui-cleanup/`

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/.runtime/pw-browsers" .venv-test/bin/python -m playwright show-trace output/playwright/stage-3-chromium-diagnostic/tests-ui-diagnostics-demo-py-test-injected-wrong-title-chromium/trace.zip
```

使用官方插件 `--screenshot=only-on-failure --tracing=retain-on-failure`，无需重复实现截图hook。成功用例默认不保留截图/Trace，首条smoke曾显式开启on用于可行性审查。Trace可能包含临时凭据，只保留本地；单独JSON网络审计不记录headers/body。

## 隔离、清理和残留检查

三轮最终UI每轮创建7个账户（访客测试无账号），销毁前文章/标签均0；账户随独立数据库删除，不设计危险的全库SQL。故障注入轮的1条文章也已API清理至0。混合轮31个账户、独立API轮24个账户均随各自数据库销毁。

三轮UI各8个独立context，创建/关闭node id列表一致；每条开始无cookie和jwtToken。browser关闭前context数为0，关闭后is_connected为false；独立ps检查未发现本工程Chromium或Playwright驱动残留。前后端进程结束，数据库与临时后端源码目录实际确认不存在。证据见browser-lifecycle.json、frontend.json、cleanup.json、verification.json和chromium-commands.json。

未观察到用例之间共享认证或顺序依赖，但未验证所有排列、并发或SIGKILL后的恢复。

## 实际问题和剩余限制

- 本阶段没有确认新的RealWorld业务产品Bug，不新增虚假的BUG-002。已知BUG-001修复及历史证据保持隔离。
- Headless Shell本机问题保留为未完全定位的环境兼容性限制；完整Chromium通道稳定通过，不表示所有浏览器模式都通过。
- 插件base_url弃用提示已通过明确fixture配置解决，未修改插件源码。
- Console/pageerror目前用于诊断，不自动将所有console错误判为失败；HTTP与UI业务断言、外部API守卫严格执行。
- 外部字体/图标资源被阻断，不进行像素或字体保真验证。
- 仅Chromium桌面、macOS、SQLite、固定版本；没有UI注册、Firefox/WebKit、移动端、并发、视频、全页面可访问性检查或CI。
- 底层服务仍有空闲端口探测竞争窗口；强制杀进程/断电不能保证finally清理。ps残留检查针对当前macOS，跨平台需适配。
- 默认output目录会被后续运行复用；证据轮次请使用新的目录。本文固定证据路径已保留。

下一阶段建议先由用户独立完成登录练习并能解释POM、context隔离和Trace定位，再确认是否推进CI。本次不开发CI、性能或测试平台，未Push、PR、部署。

官方参考：[pytest插件与fixture/产物选项](https://playwright.dev/python/docs/test-runners)、[Trace Viewer](https://playwright.dev/python/docs/trace-viewer-intro)。

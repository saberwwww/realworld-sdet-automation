# 阶段4：数据库一致性与跨层业务验证

日期：2026-11-03（Asia/Shanghai）。使用Python标准库sqlite3，无新增依赖或业务源码修改。增强现有5个测试实例，不新增重复正式用例；正式套件仍为27条API＋8条UI，共35条。

## 真实架构与数据库结构

先阅读原fixture、临时SQLite管理器、RealWorld Article/User模型、文章schema映射及创建/修改/删除API，再在真实迁移后的临时库读取PRAGMA表结构。第一次schema-check使用原注册测试，1 passed；保存schema-check/schema.json。后续每轮也保存schema.json，不依赖过时汇总猜表结构。

| 业务含义 | 实际表/字段 | 验证规则 |
|---|---|---|
| 文章主键 | articles_article.id，INTEGER PK | 修改后同一id；物理删除后无该id |
| API文章slug | articles_article.slug | 创建响应与记录一致；标题修改后采用新slug |
| 标题 | articles_article.title | 等于请求title |
| API description | articles_article.summary | 等于请求description |
| API body | articles_article.content | 等于请求body |
| 作者 | articles_article.author_id → accounts_user.id | JOIN得到username，等于本条注册用户 |
| 创建/更新时刻 | created、updated | 修改保留created；拒绝操作整行不变，不强行断言时钟差值 |

文章表没有deleted/deleted_at状态列；删除接口实际调用Article.delete()，因此断言物理删除。实际SQLite外键元数据为NO ACTION，不能把Django模型里的on_delete行为直接描述成SQLite数据库级CASCADE。本阶段没有测试删除用户或级联删除。

## 路径来源与只读查询方案

管理器现在yield不可变BackendEnvironment(api_url, database)。session fixture backend_environment持有它，原api_url fixture只转发URL；API和UI调用方式不变。db fixture直接读取同一环境对象的路径，不从旧cleanup.json、任意环境变量或用户输入取得数据库路径。

ArticleDatabase每次查询都使用：

```python
with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                             timeout=5, isolation_level=None)) as connection:
    connection.row_factory = sqlite3.Row
    rows = [dict(row) for row in connection.execute(sql, parameters)]
```

mode=ro提供只读访问，并拒绝连接不存在的文件，避免意外建空库。每次短连接查询后显式close，不跨请求持有事务/快照。管理器的schema和结束计数连接也改为closing，避免误把sqlite3事务上下文当成自动关闭连接。

业务查询只有固定SELECT，值用`?`绑定。按slug/id读取采用LEFT JOIN保留可能的孤立文章，避免关联异常把真实存在的文章过滤掉；按作者计数使用JOIN＋WHERE＋COUNT。查询字段不含密码哈希和Token。SQL、绑定参数、观察行保存到每轮database/<测试名>.json，供审计；不写开发数据库，不用SQL替代业务动作。

## 增强的5个实例

| 原有用例 | 本次增加的跨层证据 |
|---|---|
| API test_article_crud | 创建201/JSON→数据库字段/作者/数量；同时准备另一作者对照行；API修改标题/摘要/正文→新slug、同主键、同作者、created不变、数量仍1、对照行不变；API删除204→数据库按id/新slug均不存在、数量0、对照行不变；API再查404 |
| API test_update_invalid | 422拒绝空标题后，数据库整条记录与操作前完全相同 |
| API test_non_owner_forbidden[update] | 非所有者PUT得到403，数据库整行不变 |
| API test_non_owner_forbidden[delete] | 非所有者DELETE得到403，数据库整行仍存在且不变 |
| UI test_edit_article | API准备文章，浏览器真实编辑并刷新；UI正文正确后，数据库原id的content同步更新，title/summary/作者/created及数量符合预期 |

这5条用`@pytest.mark.db`定向选择。清理fixture中的SQL计数不额外算作业务用例。没有把创建、修改、删除机械拆成重复用例；已有CRUD链路提供三个阶段证据。

## 数据准备、清理与故障注入

用户、文章准备仍通过API；UI编辑的前置文章由API创建，动作由浏览器执行。每条使用唯一UUID账户，各轮有不同临时SQLite。CRUD中的对照文章属于另一用户，用于验证非预期修改。

标题变更会改slug。旧article_factory按创建时slug清理，在本阶段新增的改名场景下不足以可靠清理。现改为在请求前登记本fixture的测试作者，通过只读查询找到其当前文章slug，再逐条调用DELETE API；最后COUNT必须为0。只针对本fixture登记的唯一测试作者，数据库查询本身没有DELETE语句。清理错误收集后明确报错，session最后还检查原始文章表总数为0。

`tests/demos/db_failure_demo.py`显式执行，不在默认收集范围：创建文章→API修改标题使slug变化→读取新行→故意断言错误标题。实际1 failed，准确显示真实标题与INTENTIONAL WRONG DATABASE TITLE的差异；后端日志确认对新slug执行DELETE 204，最后SQL COUNT为0，数据库及临时源码目录销毁。它是主动故障注入，不是新的产品Bug。

## 实际命令及结果

```bash
.venv-test/bin/python -m pytest -m db -v --evidence-dir=evidence/stage-4/db-final --junitxml=evidence/stage-4/db-final/results.xml --output=output/playwright/stage-4-db-final
.venv-test/bin/python -m pytest tests/demos/db_failure_demo.py -v --evidence-dir=evidence/stage-4/failure-cleanup --junitxml=evidence/stage-4/failure-cleanup/results.xml --output=output/playwright/stage-4-failure-cleanup
.venv-test/bin/python -m pytest tests/api -v --evidence-dir=evidence/stage-4/api-regression --junitxml=evidence/stage-4/api-regression/results.xml --output=output/playwright/stage-4-api-regression
.venv-test/bin/python -m pytest tests/ui -v --evidence-dir=evidence/stage-4/ui-regression --junitxml=evidence/stage-4/ui-regression/results.xml --output=output/playwright/stage-4-ui-regression
.venv-test/bin/python -m pytest -v --evidence-dir=evidence/stage-4/full-1 --junitxml=evidence/stage-4/full-1/results.xml --output=output/playwright/stage-4-full-1
.venv-test/bin/python -m pytest -v --evidence-dir=evidence/stage-4/full-2 --junitxml=evidence/stage-4/full-2/results.xml --output=output/playwright/stage-4-full-2
.venv-test/bin/python -m pytest --reverse-order -v --evidence-dir=evidence/stage-4/reverse --junitxml=evidence/stage-4/reverse/results.xml --output=output/playwright/stage-4-reverse
```

实际参数、退出码保存在commands.json，终端输出保存为各轮同名txt，JUnit经原有summarize_junit.py生成summary.json。没有跳过或放宽断言；故障注入单独执行且预期exit 1。

| 最终轮次 | 通过 | 失败 | 错误/跳过 | JUnit秒数 |
|---|---:|---:|---:|---:|
| db-final | 5 | 0 | 0 / 0 | 4.676 |
| failure-cleanup（注入） | 0 | 1 | 0 / 0 | 1.300 |
| api-regression | 27 | 0 | 0 / 0 | 5.287 |
| ui-regression | 8 | 0 | 0 / 0 | 11.078 |
| full-1 | 35 | 0 | 0 / 0 | 15.493 |
| full-2 | 35 | 0 | 0 / 0 | 15.006 |
| reverse | 35 | 0 | 0 / 0 | 14.850 |

定向轮另外30条是deselected，不是skipped。首次开发验证cross-layer也5条通过；之后将按主键/slug查询的关联加强为LEFT JOIN，再执行上述最终定向和完整回归。所有耗时是整轮运行，不是性能指标。

七轮数据库路径互不相同；SQL审计路径与该轮后端cleanup.json的路径一致；每轮文章计数0，临时目录已实际确认不存在，进程停止。数据库内用户随该轮数据库销毁，不向API中不存在的删除用户功能发请求。verification.json保存跨轮核验结果。没有观察到顺序依赖，但未验证所有排列或并发。

## 新增及修改文件

新增：

- tests/support/database.py：小型只读查询器、字段映射断言。
- tests/demos/db_failure_demo.py：改名后失败的清理诊断。
- docs/stage-4.md、docs/stage-4-interview.md、evidence/stage-4/。

修改：

- tests/support/server.py：环境描述对象、实际表结构证据、显式关闭SQLite连接。
- tests/conftest.py：backend_environment/api_url适配、db fixture及查询记录、支持slug变化的文章清理。
- tests/api/test_articles.py：增强4个现有实例。
- tests/ui/test_business.py：增强已有编辑实例。
- pytest.ini：登记db marker；README：当前阶段和运行说明。

未修改：开源前后端业务源码、BUG-001补丁、旧缺陷记录和历史证据、依赖锁。数据库只是Python标准库能力，不引入ORM或新数据库服务。

## 缺陷与剩余边界

本阶段未发现新的被测业务缺陷。解决了测试框架清理对“标题变化导致slug变化”的适配问题；旧阶段不含改标题，所以不倒改其历史通过结论。

当前只证明本地SQLite同步请求模型下的这些字段/记录一致性，不覆盖PostgreSQL、异步落库、并发事务、隔离级别、复杂关联/级联、标签/评论一致性、用户删除或性能。部分数据库清理定位与业务检查复用查询器，属于白盒测试依赖；若表结构变化需同步评审，API契约测试仍独立存在。

fixture只读查询可能暴露真实数据库的中间状态，本项目每次操作在HTTP响应完成后查询且连接短生命周期；没有跨多SQL语句的事务快照一致性测试。独立临时环境不代表任意外部环境可安全使用此框架。

下一步建议先完成面试文档中的独立SQLite练习，能自己解释参数绑定、LEFT JOIN、主键与slug区别，以及失败后的清理，再确认是否推进CI。本阶段已停止，未开发CI、性能/管理平台，未Push或公网部署。

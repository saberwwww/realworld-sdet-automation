# 阶段4：数据库一致性与跨层验证面试讲解

本阶段没有增加正式用例数。增强现有4个API实例和1个UI实例，正式套件仍为27条API＋8条UI。业务动作仍走真实HTTP或浏览器，sqlite3只负责读取独立测试库。

## 1. 为什么接口返回200不代表业务一定成功？

状态码只是服务对请求的声明。实现有问题时，可能先拼出成功响应，却没有保存，或者保存了错误正文、改错用户的记录。只断言200看不到这些错误。

我们的创建接口按契约应为201，而不是200。`test_article_crud`先验证201和JSON，再用响应slug查数据库，核对title、summary、content和作者。修改后既GET接口再查，又按原数据库主键查新值；删除后既查API404，又查数据库主键不存在。这些是不同层面的证据。

数据库正确也不能替代UI断言：前端可能没有正确展示。`test_edit_article`保留真实点击、页面刷新和正文断言，再额外核对数据库content。

## 2. 如何测试API和数据库一致性？

先确认字段映射，而不是假设JSON字段与列名一样。本项目真实迁移后：

| API | 数据库 |
|---|---|
| article.slug | articles_article.slug |
| article.title | articles_article.title |
| article.description | articles_article.summary |
| article.body | articles_article.content |
| article.author.username | 用author_id关联accounts_user.id得到username |

看`tests/support/database.py`里的`assert_stored_article`，它按这个映射逐项比较。SQL结构来自模型、schema和实际PRAGMA结果，实际结果保存在每轮schema.json。

标题修改会改变slug，所以更新前记住内部id，再按id读回来；验证id、author_id、created不变且本作者记录数仍为1，防止把“新增一条替代旧记录”误认为正常UPDATE。旧slug在数据库里不再匹配，新slug和响应一致。

本阶段不直接执行SQL UPDATE或DELETE；这样才能验证业务代码是否真的保存和删除。

## 3. 测试数据为什么需要隔离？

两个测试用同一标题、账号或数据库，可能互相覆盖，或者上次留下的记录让本次产生假通过。即使浏览器context隔离，也不会自动隔离数据库。

本项目每轮创建新的临时SQLite和后端源码副本；每个测试通过UUID生成唯一用户。CRUD用例还创建另一作者的对照文章，修改/删除目标文章之后完整比较对照行，证明没有观察到误改其他作者记录。

不同轮次的主键可以都从1开始，这是正常的；要一起看数据库路径和主键，不能只用id判断是否同一条业务数据。

## 4. fixture怎样保证测试结束后清理？

`article_factory`在发创建请求前登记测试作者。yield把create函数交给测试；无论断言成功或失败，正常pytest teardown都会执行yield后逻辑。

重要变化是清理不能永远使用创建时的slug。标题修改后slug会变，我们从本轮只读数据库按唯一作者查询当前文章，再用当前slug和该作者Token发DELETE，最后用SQL COUNT确认0条。SQL用于定位和验证，删除仍通过API。

本阶段故意在改名成功后断言错误标题，真实产生1条FAILED；后续清理日志仍显示新slug被删除、文章数为0，临时数据库销毁。这是故障注入，不是产品Bug。

`BackendEnvironment`是session fixture，依赖它的测试和数据库检查完成后才停止后端、审计并销毁临时目录。SIGKILL或断电不能保证finally，这个边界不能夸大。

## 5. 接口成功但数据库没记录，怎么查？

先别立刻改断言或宣布产品Bug，按顺序查：

1. 请求实际发到哪个api_url？数据库路径是否来自同一个backend_environment？不要从旧报告中复制路径。
2. 字段映射、查询条件是否正确？标题变化可能导致旧slug失效，应按原id检查。
3. 数据库连接是否误建了空库？本项目mode=ro在文件不存在时会失败，不会悄悄创建。
4. 是否持有旧事务快照？本项目每次查询新建连接、读完立即关闭，不跨HTTP请求保留读事务。
5. 再看服务端日志：是否保存/提交异常，是否错误地返回了成功？本项目Django请求中的写入同步完成；若系统本身是异步落库，需按明确业务时限设计等待，不能随便sleep。
6. 独立重现，只读查询原始行，判断是测试配置、SQL条件还是业务持久化问题。

`database/<测试名>.json`保存参数化SQL、绑定参数和读取结果，便于和HTTP/UI断言对应。这里只查询测试文章字段和作者名，不输出密码哈希或Token。

## 6. 如何防止污染开发环境？

连接路径只从运行中管理器生成的`BackendEnvironment.database`传给db fixture。没有DATABASE_PATH命令行选项，也不读取旧cleanup.json来定位数据库；测试忽略外部API_BASE_URL。

sqlite3采用 `path.as_uri() + "?mode=ro"` 和 `uri=True`。查询模块没有业务写操作，每次用contextlib.closing显式关闭连接。注意：`with sqlite3.connect(...) as conn`通常管理的是事务，不是自动close连接；因此这里显式closing很重要。

用户不能删除时，最后销毁本轮临时数据库，而不是执行全库DELETE。原来的`.runtime/realworld.sqlite3`演示库不在这个路径中。只读访问防止写污染，但不能防止误读其他环境，所以路径来源隔离同样必要。

## 7. SELECT、WHERE、JOIN分别做什么？

SELECT选择需要的列，例如id、title、content；不需要为了检查文章就SELECT用户的password。WHERE筛选当前文章或作者；`?`占位符把值作为数据绑定，不拼接用户输入。

JOIN关联文章和作者，用于验证文章属于正确用户。`ARTICLE_SELECT`采用LEFT JOIN：即使作者关联异常，也保留文章行，让author_username变成None并触发断言，而不是因为INNER JOIN过滤掉孤立文章而误认为“文章不存在”。按作者统计时使用JOIN和WHERE，得到该作者的记录数量。

```sql
SELECT a.id, a.slug, a.title, a.content, u.username
FROM articles_article AS a
LEFT JOIN accounts_user AS u ON u.id = a.author_id
WHERE a.slug = ?;
```

COUNT(*)用于检查数量，例如更新前后均1条、删除/清理后0条。参数绑定只适用于值，不能把整段SQL或表名当成一个`?`；本项目业务SQL的表名列名是核对后的固定常量。

## 8. 哪些代码应能独立写出来？

建议能不用AI写出：

- 使用sqlite3和contextlib.closing连接已知测试库，设置Row，执行带`?`参数的SELECT。
- 用fetchone/列表结果判断记录是否存在，把字段与预期字典比较。
- 写一条文章表与用户表的LEFT JOIN，以及按作者COUNT的SQL。
- 写API创建→取slug→SQL核对的短测试；能解释“准备/动作/断言”三步。
- 写yield fixture，清理属于自己的资源，并检查清理失败而不是吞掉异常。

对应真实代码：ArticleDatabase._query、by_slug、by_id、count_for_author、assert_stored_article，以及test_article_crud。复杂的服务管理器不是本阶段要求背诵的重点。

## 独立小练习：只读查询一条真实文章（20–30分钟）

关闭AI补全。自行创建`tests/api/exercise_db.py`，不以test_命名，避免默认收集。写一个函数：

```python
def test_exercise_database(api, owner, article_factory, backend_environment):
    # 1. 用article_factory(owner)通过真实API创建文章，断言201，取slug。
    # 2. 从backend_environment.database取得本轮库路径。
    # 3. 自己用sqlite3 + closing + mode=ro连接，不能调用现有db工具替你查询。
    # 4. 写参数化SELECT，按slug读取id、title、summary、content、author_id。
    # 5. 断言记录存在，字段分别等于创建请求的title、description、body。
    # 6. 加一道LEFT JOIN核对作者username。
    # 不执行SQL写入；测试退出时article_factory负责清理。
    ...
```

```bash
.venv-test/bin/python -m pytest tests/api/exercise_db.py -v --evidence-dir=.runtime/exercise-db
```

验收：不硬编码某次临时库路径、不用字符串拼接slug、不连接开发库；说清Row、fetchone、占位符和closing的作用。最后临时库应已销毁，所以必须在fixture存活期间查询。这个练习文件留给你独立完成，本次未生成或执行，不计为已通过测试。

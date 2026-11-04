# 阶段 2.5：BUG-001 本地修复闭环

日期：2026-11-03（Asia/Shanghai）。本次只处理 BUG-001 和必要认证边界，没有 UI、CI、性能平台、依赖升级或远程操作。

完整缺陷证据链在 [BUG-001](bugs/BUG-001-invalid-token-500.md)，通俗解释和一分钟讲法在 [面试文档](stage-2.5-interview.md)。

## 结论

真实根因是 RealWorld 主 NinjaAPI 缺失 jwt_ninja.errors.APIError 的异常转换。异常携带 401 并不自动使 HTTP 返回 401；它不属于已处理的 HttpError，最终落到默认 500。测试请求头正确，原始用例未放宽，环境迁移和合法身份控制正常。

独立补丁只向 `config/urls.py` 增加 import 和一个专用 handler（6 行新增含空行），没有修改认证、验签或权限判断。status 采用异常的 http_status_code，不固定写死 401。原始 upstream/backend 工作区保持干净。

## 可复现的两个变体

`tests/support/server.py` 从 config/upstream.json 的固定 commit 导出临时源码：

- `--backend-variant=baseline`：原始未修复源码。
- `--backend-variant=fixed`：对临时源码应用 patches/BUG-001.patch。**现在为默认值**。

两者都新建独立数据库、迁移、启动回环端口服务。原始克隆和阶段 0 的手动演示服务不被修改。每轮 cleanup.json 记录变体、固定 commit，fixed 额外记录补丁 SHA256。所有测试仍发真实 HTTP。

## 实际命令

以下命令均已执行，对应日志、XML 和 cleanup.json 在所指 evidence 目录。baseline 失败是本次实验的对照，不要用 `&&` 把后续回归阻断。

```bash
# 先验证整个新套件在未修复版本上的行为
.venv-test/bin/python -m pytest -v --backend-variant=baseline --evidence-dir=evidence/stage-2.5/before --junitxml=evidence/stage-2.5/before/results.xml
# 独立稳定复现原缺陷
.venv-test/bin/python -m pytest -v 'tests/api/test_users.py::test_protected_user[invalid-token]' --backend-variant=baseline --evidence-dir=evidence/stage-2.5/baseline-repro --junitxml=evidence/stage-2.5/baseline-repro/results.xml
# 新增认证边界
.venv-test/bin/python -m pytest -v tests/api/test_auth_boundaries.py --backend-variant=fixed --evidence-dir=evidence/stage-2.5/fixed-auth --junitxml=evidence/stage-2.5/fixed-auth/results.xml
# 原有20条，测试文件未改动
.venv-test/bin/python -m pytest -v tests/api/test_users.py tests/api/test_articles.py --backend-variant=fixed --evidence-dir=evidence/stage-2.5/fixed-original --junitxml=evidence/stage-2.5/fixed-original/results.xml
# 全量连续两次及反序
.venv-test/bin/python -m pytest -v --backend-variant=fixed --evidence-dir=evidence/stage-2.5/fixed-run-1 --junitxml=evidence/stage-2.5/fixed-run-1/results.xml
.venv-test/bin/python -m pytest -v --backend-variant=fixed --evidence-dir=evidence/stage-2.5/fixed-run-2 --junitxml=evidence/stage-2.5/fixed-run-2/results.xml
.venv-test/bin/python -m pytest -v --backend-variant=fixed --reverse-order --evidence-dir=evidence/stage-2.5/fixed-reverse --junitxml=evidence/stage-2.5/fixed-reverse/results.xml
# 独立故障注入探针，直接验证异常分发而非HTTP业务
.venv-test/bin/python scripts/probe_bug001_dispatch.py > evidence/stage-2.5/dispatch-probe.json
```

summary.json 由已有 scripts/summarize_junit.py 解析这七份 XML 生成；commands.json 记录独立复现和修复后各轮的实际参数与退出码（首次 before 轮在此前单独执行，exit 1）。

| 轮次 | passed | failed | skipped | errors | 秒 |
|---|---:|---:|---:|---:|---:|
| before | 22 | 5 | 0 | 0 | 5.503 |
| baseline-repro | 0 | 1 | 0 | 0 | 1.123 |
| fixed-auth | 7 | 0 | 0 | 0 | 2.328 |
| fixed-original | 20 | 0 | 0 | 0 | 3.912 |
| fixed-run-1 | 27 | 0 | 0 | 0 | 5.107 |
| fixed-run-2 | 27 | 0 | 0 | 0 | 5.139 |
| fixed-reverse | 27 | 0 | 0 | 0 | 5.248 |

故障注入探针另验 APIError 401→401、APIError 400→400、RuntimeError→500，三项断言成功。该探针不计入27条正式测试，也不是新发现的产品Bug。

七轮临时进程均停止，文章计数为0，数据库及源码临时目录均已确认不存在。详见 provenance.json 和各轮 cleanup.json。当前没有观察到注册、登录、文章 CRUD、401/403 权限回归。

## 核心新增和修改

- 新增 patches/BUG-001.patch：唯一业务变更的独立可审查补丁。
- 修改 tests/support/server.py、tests/conftest.py：基线/修复变体选择，固定 commit 导出，临时应用补丁与来源记录。
- 新增 tests/api/test_auth_boundaries.py：7 条认证输入边界；真实有效 Token 先做对照。
- 新增 tests/support/mint_expired.py：仅本地测试用的可靠过期 Token 构造，不访问数据库，不输出密钥。
- 新增 scripts/probe_bug001_dispatch.py：异常类型/状态分发边界探针。
- 更新缺陷记录、README；新增本阶段报告与面试文档，保留阶段2历史证据。

## 未覆盖与限制

结论仅对本机固定版本、SQLite、DEBUG=True成立。/auth 刷新/撤销、过期会话、停用用户、可选认证接口、生产环境和 PostgreSQL 尚未完整验证。主 API 的 APIError handler 也能覆盖 /auth 路由，这是明确的剩余回归范围；未凭当前测试宣称所有认证功能均无问题。

已知阶段2的端口探测竞争窗口、强制杀进程后的清理限制继续存在，未为了本次修复扩展框架。默认日志目录会覆盖，保留实验请使用新的 evidence 目录。上游原始版本没有被“永久修复”，手动 backend.sh 仍运行原始版本；需要另行决定是否将补丁用于演示或贡献上游。

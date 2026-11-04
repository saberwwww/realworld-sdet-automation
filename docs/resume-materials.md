# 简历素材（截至阶段5真实云端验证）

**项目：Web业务系统自动化测试与质量保障**  
**技术栈：Python、pytest、requests、Playwright Python、SQLite/SQL、GitHub Actions、Git**

- 基于开源RealWorld Vue3/Django Ninja业务系统，独立开发分层自动化测试工程，覆盖注册登录、认证边界、文章CRUD与权限校验，形成27条API及8条UI测试，本地补丁版本全量35/35通过。
- 使用pytest fixture、参数化、独立浏览器context与临时SQLite实现环境及数据隔离；增强5条现有用例，以只读参数化SQL验证创建、更新、删除及拒绝操作后的数据一致性。
- 通过非法Token测试发现服务端500，结合异常堆栈定位JWT异常处理缺失，在隔离源码副本实施最小补丁并完成回归，保留未修复基线及失败证据。
- 编写GitHub Actions工作流和统一安装/执行脚本，固定上游源码及依赖，生成JUnit报告，失败保留截图、Trace及服务日志；已在GitHub托管Ubuntu runner真实执行35条测试并全部通过；定位并修复Chromium临时socket路径过长的Linux环境问题。

## 使用边界

不得删去“基于开源”与“独立测试工程”的区别。5条SQL增强包含于35条，不是40条；不是企业项目、上线系统或上游已合并修复。没有业务用户量、团队规模、性能提升比例或测试效率百分比的证据，不写这些数字。

简历篇幅不足时可合并第2/4条。可写“真实Linux CI全量35/35通过”，不能将少量运行夸大为长期稳定性结论。[已验证运行](https://github.com/saberwwww/realworld-sdet-automation/actions/runs/41756762324)，对应提交ad4331fc1e6360a3fd50065098759d29cc5d114d，报告和日志已下载留存。

面试时展示 docs/verification-summary.json、测试核心函数及本地报告，避免公开包含Token的原始Trace。本人需要能够独立解释代码，不能只背这四条文字。

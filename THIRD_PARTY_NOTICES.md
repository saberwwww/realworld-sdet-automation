# 第三方来源

固定版本的机器可读来源见 config/upstream.json，下载代码位于被 Git 忽略的 upstream/。

| 对象 | 原始来源 | 固定 commit | 许可证副本 |
| --- | --- | --- | --- |
| Django Ninja 后端 | https://github.com/c4ffein/realworld-django-ninja | 87dd078c883a046f5ff20269df2fb004d8b5f83f | licenses/realworld-backend-MIT.txt |
| Vue3 前端 | https://github.com/realworld-apps/vue-realworld-example-app | db749e3bb1a45755e0a3f4065abaf7346f004f36 | licenses/realworld-frontend-MIT.txt |
| RealWorld 规范子模块 | https://github.com/realworld-apps/realworld | 25588846c314b15a5e427ffe816e6b4af7be68c7 | licenses/realworld-spec-MIT.txt |

保留原版权和 MIT 文本。业务代码属于相应开源贡献者；tests/、scripts/、本项目文档与工作流是独立测试工程，不能将完整业务系统描述为个人开发。

patches/BUG-001.patch 是针对上述后端 commit 的本地实验补丁，未提交或合并上游。依赖的许可证以各依赖分发包为准。未擅自替项目所有者选定个人测试代码的开源授权；公开复用前由所有者选择并添加适合的 LICENSE。公开可见不自动意味着已授予开源许可证。

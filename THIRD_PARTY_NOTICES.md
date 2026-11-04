# 第三方来源

固定版本的机器可读来源见 config/upstream.json，下载代码位于被 Git 忽略的 upstream/。

| 对象 | 原始来源 | 固定 commit | 许可证副本 |
| --- | --- | --- | --- |
| Django Ninja 后端 | https://github.com/c4ffein/realworld-django-ninja | 87dd078c883a046f5ff20269df2fb004d8b5f83f | licenses/realworld-backend-MIT.txt |
| Vue3 前端 | https://github.com/realworld-apps/vue-realworld-example-app | db749e3bb1a45755e0a3f4065abaf7346f004f36 | licenses/realworld-frontend-MIT.txt |
| RealWorld 规范子模块 | https://github.com/realworld-apps/realworld | 25588846c314b15a5e427ffe816e6b4af7be68c7 | licenses/realworld-spec-MIT.txt |

保留原版权和 MIT 文本。业务代码属于相应开源贡献者；tests/、scripts/、本项目文档与工作流是独立测试工程，不能将完整业务系统描述为个人开发。

patches/BUG-001.patch 是针对上述后端 commit 的本地实验补丁，未提交或合并上游。依赖的许可证以各依赖分发包为准。未擅自替项目所有者选定个人测试代码的开源授权；公开复用前由所有者选择并添加适合的 LICENSE。公开可见不自动意味着已授予开源许可证。


## 项目自身许可证：待所有者决定

当前根目录没有LICENSE，GitHub的licenseInfo为null。上游MIT文本仅说明上游各自的许可，不能代替原创测试工程的授权。公开展示不强制要求选择开源许可证；如果希望其他人明确获准复用、修改、分发本项目自身代码，应由所有者选定许可并放置根目录LICENSE。未授权不影响GitHub条款允许的查看、fork等行为，但不等于允许任意再分发或商用。[GitHub许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)、[无许可证的含义](https://choosealicense.com/no-permission/)。

| 选择 | 影响 |
| --- | --- |
| [MIT](https://choosealicense.com/licenses/mit/) | 宽松授权，允许商用、修改、再分发及闭源使用；保留版权和许可声明，提供免责条款，不要求公开衍生源码。 |
| [Apache-2.0](https://choosealicense.com/licenses/apache-2.0/) | 同样允许商用和闭源使用，另有明确专利授权及相关终止条款；需保留适用声明、说明修改，按条件保留NOTICE，文本更详细。 |
| 暂不添加 | 暂不授予通用开源复用许可；可继续公开展示，但不能将原创测试工程宣传为已经MIT开源。 |

本次仅说明选项，不新增LICENSE、不替所有者决定，也不把第三方版权改为个人版权。任何后续选择都应只对有权授权的原创部分作出，继续保留第三方来源及原许可证。

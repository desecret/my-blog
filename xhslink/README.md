# xhslink 模块结构

当前后端结构按职责拆分为 4 层：

- `server.py`: Flask 路由入口，仅处理 HTTP 请求和响应拼装
- `app_config.py`: 全局配置与默认常量
- `redirect_store.py`: 中间页 key 映射与统计数据读写
- `sign_service.py`: x-s / x-t 签名服务
- `short_url_task.py`: 调用小红书短链接口生成 short_url

## 运行方式

在项目根目录执行：

```bash
python xhslink/server.py
```

服务默认监听 `http://127.0.0.1:9999`。

## 维护建议

- API 路由改动优先在 `server.py`
- 配置字段新增优先在 `app_config.py` 的 `DEFAULT_REDIRECT_CONFIG`
- 统计和历史逻辑放在 `redirect_store.py`
- 签名逻辑变更放在 `sign_service.py`

## 数据库存储（第一阶段）

当前仓库已提供 SQLite 表结构和 JSON 迁移脚本，便于从 `redirect-config.json` 平滑迁移：

- 表结构文件：`xhslink/db_schema.sql`
- 迁移脚本：`xhslink/migrate_json_to_db.py`
- 默认数据库：`data/xhslink.db`

### 执行迁移

在项目根目录执行：

```bash
python xhslink/migrate_json_to_db.py
```

常用参数：

```bash
python xhslink/migrate_json_to_db.py --config ./redirect-config.json --db ./data/xhslink.db
python xhslink/migrate_json_to_db.py --append
```

说明：

- 默认模式是全量覆盖导入（会清空表后重建数据）
- `--append` 为追加模式（不清空表）

## 数据库主模式

当前主流程已切换为 SQLite 主读写：

- `/middle` 的 key -> target 解析读取 SQLite
- `/api/middle-url` 生成 key 与映射写入 SQLite
- `/api/short-url` 的复用判断、短链记录、生成日志写入 SQLite
- `/api/short-url-dashboard` 读取 SQLite 聚合结果

`redirect-config.json` 现在主要承担运行配置（例如 `middleBaseUrl`、`dbPath`），不再作为业务数据主存储。

运行约束：

- `redirect-config.json` 在服务运行时按只读配置处理，代码不会再写回该文件。

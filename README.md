# epg

GitHub Actions 每 12 小时把原站的 **1 天 / 3 天 / 9 天** 三份 XMLTV 节目单分别去广告、按官方频道清单改名，打包后发布到 `epg` 分支。路由器不用再解压 19 MB / 过滤 40 万行。

## 订阅

| 天数 | 地址 |
| --- | --- |
| 1 天 | `https://raw.githubusercontent.com/TW20022/epg/epg/1day.xml.gz` |
| 3 天 | `https://raw.githubusercontent.com/TW20022/epg/epg/3days.xml.gz` |
| 9 天 | `https://raw.githubusercontent.com/TW20022/epg/epg/9days.xml.gz` |

播放器支持 `.gz` 且能直连外网时，**填一条就够了，路由器什么都不用装**。每份都有同名 `.meta.json`（构建时间、频道数、删除条数、sha256）。`epg.xml.gz` / `meta.json` 是 9 天版的兼容别名，旧订阅地址不会失效。国内访问 raw 不稳时，把前缀换成 `https://cdn.jsdelivr.net/gh/TW20022/epg@epg/`。

## 自动更新

全部配置只有 `.github/workflows/epg.yml` 一个文件：定时 UTC 04:00 / 16:00（北京 12:00 / 00:00）、push main 触发，也能手动 `Run workflow`。Build 步一个循环依次处理三份源（`--source-url ... --name <天数>`），Publish 步把 3 份成品 + 3 份 meta + 2 个别名一起推到 `epg` 分支。

- 内置 `GITHUB_TOKEN`，无需任何密钥；公开仓库 Actions 免费。
- 每次孤儿单 commit + force push，`epg` 分支永远只有一个提交。
- 任一源失败就整次不发布，已有成品不受影响。

## 路由器不需要脚本

只是想让局域网设备用本地路径的话，crontab 加一行（把 `9days` 换成 `1day` / `3days` 即可）：

```sh
0 1,13 * * * mkdir -p /tmp/epg && wget -q -T 60 -O /tmp/epg/.epg.new https://raw.githubusercontent.com/TW20022/epg/epg/9days.xml.gz && gzip -t /tmp/epg/.epg.new && mv -f /tmp/epg/.epg.new /tmp/epg/epg.xml.gz
```

「临时文件 → `gzip -t` → `mv`」是为了下载失败时不覆盖旧成品，比脚本本身重要。播放器只认明文 `.xml` 时末尾再接 `&& gzip -dc /tmp/epg/epg.xml.gz > /tmp/epg/epg.xml`（多占约 19 MB 内存）。`/tmp` 重启会清空，定时任务会重建；证书报错就 `opkg install ca-certificates`。

## 文件

| 文件 | 作用 |
| --- | --- |
| `.github/workflows/epg.yml` | 唯一配置：定时、三次构建、发布 |
| `scripts/build_epg.py` | 下载、去广告、改名、打包，仅 Python 3 标准库 |
| `LICENSE` | MIT |

本地调试：`python3 scripts/build_epg.py --source-url https://epg.136605.xyz/3days.xml.gz --name 3days --out-dir out`，参数见 `--help`。

## 处理内容

三份包共用同一规则：整块删除服务方水印、广告/购物标题、≤1 秒跨天占位；把数字 channel id 换成 `context.txt` 的标准频道名，同步改 `<programme>` 引用，原数字 id 保留为别名。实测频道数 439 / 440 / 639，引用缺失均为 0，三份合计构建约 10 秒（以各份 `meta.json` 为准）。

## 说明

数据源 `epg.136605.xyz`，版权归原服务方，本项目只做格式处理，仅供个人学习研究，请勿商用。GitHub 定时任务高峰期可能延迟。

MIT © 2026 TW20022

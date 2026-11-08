# epg

GitHub Actions 每 12 小时把 9 天 XMLTV 节目单**去广告 + 按官方频道清单改名**，打包成约 1.3 MB 的 `epg.xml.gz` 发布到 `epg` 分支。路由器不用再解压 19 MB / 过滤 40 万行。

## 订阅

```
https://raw.githubusercontent.com/TW20022/epg/epg/epg.xml.gz
https://raw.githubusercontent.com/TW20022/epg/epg/meta.json
```

播放器支持 `.gz` 且能直接访问外网时，**填第一条就够了，路由器什么都不用装**。`meta.json` 记录构建时间、频道数、删除条数与 sha256。国内访问 raw 不稳时可改用 jsDelivr：`https://cdn.jsdelivr.net/gh/TW20022/epg@epg/epg.xml.gz`

## 自动更新

全部配置只有 `.github/workflows/epg.yml` 一个文件：

- 定时 UTC 04:00 / 16:00（北京 12:00 / 00:00），push 到 main 也会触发，还能在 Actions 页面手动 `Run workflow`。
- 用内置 `GITHUB_TOKEN` 发布，**无需配置任何密钥**；公开仓库 Actions 免费。
- 每次是孤儿单 commit + force push，`epg` 分支永远只有一个提交，仓库不膨胀。
- 构建失败就不发布，已有的成品不受影响。

## 路由器不需要脚本

只是想让局域网设备用本地路径的话，crontab 加一行即可（比云端晚 1 小时，避开 Actions 排队）：

```sh
0 1,13 * * * mkdir -p /tmp/epg && wget -q -T 60 -O /tmp/epg/.epg.new https://raw.githubusercontent.com/TW20022/epg/epg/epg.xml.gz && gzip -t /tmp/epg/.epg.new && mv -f /tmp/epg/.epg.new /tmp/epg/epg.xml.gz
```

「下载到临时文件 → `gzip -t` 校验 → `mv`」是为了下载中断或拿到错误页时**不覆盖旧成品**，这三点比脚本本身重要。播放器只认 `.xml` 明文时，末尾再接 `&& gzip -dc /tmp/epg/epg.xml.gz > /tmp/epg/epg.xml`（多占约 19 MB 内存）。`/tmp` 重启会清空，定时任务会重建；HTTPS 证书报错就 `opkg install ca-certificates`。

## 文件

| 文件 | 作用 |
| --- | --- |
| `.github/workflows/epg.yml` | 定时、构建、发布（唯一配置） |
| `scripts/build_epg.py` | 下载、去广告、改名、打包，仅用 Python 3 标准库 |
| `LICENSE` | MIT |

本地调试：`python3 scripts/build_epg.py --out-dir out && gzip -t out/epg.xml.gz`，参数见 `--help`。

## 处理内容

整块删除服务方水印、广告/购物标题、≤1 秒跨天占位；把数字 channel id 换成 `context.txt` 的频道标准名，同步改 `<programme>` 引用，原数字 id 保留为别名。实测 639 频道 / 改名 638 / 保留约 12.4 万条 / 删除约 9 千条 / 引用缺失 0，构建约 6~10 秒（源站数据每次略有浮动，以 `meta.json` 为准）。

## 说明

数据源 `epg.136605.xyz`，版权归原服务方，本项目只做格式处理，仅供个人学习研究，请勿商用。GitHub 定时任务高峰期可能延迟；若境外 runner 访问不了源站，构建会失败（旧成品仍在），此时重跑一次或改用自托管 runner。

MIT © 2026 TW20022

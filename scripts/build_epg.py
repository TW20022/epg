#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_epg.py —— GitHub Actions / 任意 CI 主机用的 EPG 构建器

流程：
  下载 https://epg.136605.xyz/{1day,3days,9days}.xml.gz 之一 与 context.txt（官方频道清单）
  -> 单遍流式处理：去除广告/水印/1 秒占位、把数字 channel id 改成清单标准名
  -> 输出 <name>.xml.gz + <name>.meta.json（--plain 时另有 <name>.xml 明文）

设计要点：
  * 全程按 bytes 处理，不做编码转换，产物与 epg-update.sh 里的 awk 版本逐字节一致。
  * 单遍流式，内存只需缓存一个 <channel> / <programme> 块（几行），峰值 < 20 MB。
  * gzip 输出 mtime=0，同样的输入会得到同样的 gz，便于判断是否真的变化。
  * 只依赖 Python 3 标准库，无需 pip install。

用法：
  python3 build_epg.py                                  # 默认 9days，输出 out/epg.*
  python3 build_epg.py --source-url https://epg.136605.xyz/1day.xml.gz --name 1day
  python3 build_epg.py --gz 1day.xml.gz --ctx context.txt --name 1day --plain
  python3 build_epg.py --no-wm --no-ads --no-tiny      # 关闭某类清理
  python3 build_epg.py --no-rename                    # 保留原始数字 id
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

URL_GZ = "https://epg.136605.xyz/9days.xml.gz"
URL_CTX = "https://epg.136605.xyz/context.txt"
UA = "Mozilla/5.0 (compatible; EPG-Builder/1.0)"

# 与 epg-update.sh 的 awk 中 is_ad() 完全一致
AD_WM = [s.encode("utf-8") for s in ("提供节目单服务", "https://", "http://")]
AD_KW = [s.encode("utf-8") for s in ("广告", "選購", "选购", "現金券", "现金券")]

RE_ID = re.compile(rb'id="[^"]*"')
RE_CHAN = re.compile(rb'channel="[^"]*"')
RE_START = re.compile(rb'start="(\d{14})')
RE_STOP = re.compile(rb'stop="(\d{14})')


def fetch(url, dest, retries=3, timeout=120):
    """下载到 dest，失败重试；返回字节数。"""
    last = None
    for i in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            n = os.path.getsize(dest)
            if n == 0:
                raise ValueError("空文件")
            return n
        except Exception as e:
            last = e
            print("下载失败(第 %d 次) %s: %s" % (i, url, e), file=sys.stderr)
            if i < retries:
                time.sleep(3)
    raise RuntimeError("无法下载 %s: %s" % (url, last))


def tagtext(line):
    """取 <tag ...>text</tag> 中的 text；与 awk 的 tagtext() 一致。"""
    p = line.find(b">")
    if p < 0:
        return b""
    t = line[p + 1:]
    q = t.find(b"<")
    return t if q < 0 else t[:q]


def is_ad(t, drop_wm=True, drop_ads=True):
    if drop_wm and any(k in t for k in AD_WM):
        return True
    if drop_ads and any(k in t for k in AD_KW):
        return True
    return False


def is_tiny(st, sp):
    """复刻 awk 的 <=1 秒判断（同分钟且秒差 0/1，或起止完全相同）。"""
    if not st or not sp:
        return False
    if st == sp:
        return True
    if st[:12] == sp[:12]:
        d = int(sp[12:14]) - int(st[12:14])
        return 0 <= d <= 1
    return False


def process(gz_path, ctx_names, out_xml, out_gz, opt):
    """单遍流式处理，返回统计 dict。"""
    idmap = {}          # 原数字 id -> 标准名（未改名的为 b""）
    used = set()        # 已占用的标准名，防止 id 冲突
    st = dict(renamed=0, kept=0, dropped=0, skipped=0, channels=0,
              bad_refs=0, ad_hits=0, tiny_hits=0)

    plain = open(out_xml, "wb") if out_xml else None
    with gzip.GzipFile(out_gz, "wb", compresslevel=9, mtime=0) as zout:
        def emit(line):
            if plain:
                plain.write(line)
            zout.write(line)

        in_ch, ch_buf, oldid, cname = False, [], b"", b""
        in_prog, prog_buf, drop = False, [], False

        with gzip.open(gz_path, "rb") as src:
            for raw in src:
                # channel 块 -------------------------------------------------
                if not in_ch and not in_prog and b"<channel id=" in raw:
                    in_ch, ch_buf = True, [raw]
                    m = RE_ID.search(raw)
                    oldid = m.group(0)[4:-1] if m else b""
                    cname = b""
                    continue

                if in_ch:
                    ch_buf.append(raw)
                    if not cname and b"<display-name" in raw:
                        cname = tagtext(raw)
                    if b"</channel>" in raw:
                        ok = bool(opt.rename and cname)
                        if ok and cname not in ctx_names:
                            ok = False
                        if ok and cname in used:
                            ok = False
                        if ok:
                            used.add(cname)
                            idmap[oldid] = cname
                            ch_buf[0] = RE_ID.sub(b'id="' + cname + b'"', ch_buf[0], count=1)
                            st["renamed"] += 1
                        else:
                            idmap[oldid] = b""
                            st["skipped"] += 1
                        st["channels"] += 1
                        for i, line in enumerate(ch_buf):
                            if ok and i == len(ch_buf) - 1:
                                emit(b"    <display-name>" + oldid + b"</display-name>\n")
                            emit(line)
                        in_ch, ch_buf = False, []
                    continue

                # programme 块 -----------------------------------------------
                if not in_prog and b"<programme " in raw:
                    in_prog, prog_buf, drop = True, [], False
                    line = raw
                    m = RE_CHAN.search(line)
                    cid = m.group(0)[9:-1] if m else b""
                    nn = idmap.get(cid, b"")
                    if cid and cid not in idmap:
                        st["bad_refs"] += 1
                    if nn:
                        line = RE_CHAN.sub(b'channel="' + nn + b'"', line, count=1)
                    if opt.tiny:
                        a, b = RE_START.search(line), RE_STOP.search(line)
                        if a and b and is_tiny(a.group(1), b.group(1)):
                            drop = True
                            st["tiny_hits"] += 1
                    prog_buf.append(line)
                    continue

                if in_prog:
                    prog_buf.append(raw)
                    if b"<title" in raw and is_ad(tagtext(raw), opt.wm, opt.ads):
                        if not drop:
                            st["ad_hits"] += 1
                        drop = True
                    if b"</programme>" in raw:
                        if drop:
                            st["dropped"] += 1
                        else:
                            for line in prog_buf:
                                emit(line)
                            st["kept"] += 1
                        in_prog, prog_buf, drop = False, [], False
                    continue

                emit(raw)   # <tv>、</tv>、XML 声明等

    if plain:
        plain.close()
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-url", default=URL_GZ, help="EPG 压缩包 URL（默认 9days）")
    ap.add_argument("--name", default="epg", help="输出文件名前缀，如 1day / 3days / 9days")
    ap.add_argument("--gz", help="本地 .xml.gz（不联网，用于离线测试）")
    ap.add_argument("--ctx", help="本地 context.txt（不联网）")
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--plain", action="store_true", help="同时输出明文 <name>.xml")
    ap.add_argument("--no-rename", action="store_true")
    ap.add_argument("--no-wm", action="store_true")
    ap.add_argument("--no-ads", action="store_true")
    ap.add_argument("--no-tiny", action="store_true")
    a = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", a.name):
        ap.error("--name 只能包含字母、数字、_ . -")

    class Opt:
        rename = not a.no_rename
        wm = not a.no_wm
        ads = not a.no_ads
        tiny = not a.no_tiny
    opt = Opt()

    os.makedirs(a.out_dir, exist_ok=True)
    # 下载缓存用隐藏文件名，避免与成品混在一起
    gz = a.gz or os.path.join(a.out_dir, ".src-%s.xml.gz" % a.name)
    ctx_path = a.ctx or os.path.join(a.out_dir, ".context.txt")
    source = a.gz or a.source_url
    if not a.gz:
        print("[%s] 下载 %s ..." % (a.name, a.source_url))
        print("  得到 %d 字节" % fetch(a.source_url, gz))
    if not a.ctx:
        print("[%s] 下载 %s ..." % (a.name, URL_CTX))
        fetch(URL_CTX, ctx_path)

    ctx_raw = open(ctx_path, "rb").read()
    ctx_names = set(x.strip() for x in ctx_raw.split("，".encode("utf-8")) if x.strip())
    print("[%s] 清单名称: %d 个（去重后）" % (a.name, len(ctx_names)))

    out_gz = os.path.join(a.out_dir, a.name + ".xml.gz")
    out_xml = os.path.join(a.out_dir, a.name + ".xml") if a.plain else None
    t0 = time.perf_counter()
    st = process(gz, ctx_names, out_xml, out_gz, opt)
    elapsed = time.perf_counter() - t0

    # 完整性校验：以 </tv> 收尾，且 programme 引用全部有对应的 channel 定义
    with gzip.open(out_gz, "rb") as f:
        head = f.read(200)
        f.seek(-200, 2)
        tail = f.read()
    if b"<tv" not in head or b"</tv>" not in tail:
        raise RuntimeError("生成的 XML 不完整")
    if st["bad_refs"]:
        raise RuntimeError("有 %d 条 programme 引用了未定义的 channel" % st["bad_refs"])

    sha = hashlib.sha256(open(out_gz, "rb").read()).hexdigest()
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S +0800")
    meta = {
        "name": a.name,
        "built_at": now,
        "source": source,
        "channels": st["channels"],
        "renamed": st["renamed"],
        "programmes_kept": st["kept"],
        "programmes_dropped": st["dropped"],
        "ad_titles": st["ad_hits"],
        "tiny_slots": st["tiny_hits"],
        "bad_refs": st["bad_refs"],
        "elapsed_sec": round(elapsed, 2),
        "sha256": sha,
        "gz_bytes": os.path.getsize(out_gz),
    }
    with open(os.path.join(a.out_dir, a.name + ".meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    for k, v in meta.items():
        print("  %-20s %s" % (k, v))
    print("[%s] 完成，用时 %.2f 秒" % (a.name, elapsed))


if __name__ == "__main__":
    main()

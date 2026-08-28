import xmltodict, json, os

with open("e.xml", encoding="utf-8") as f:
    data = xmltodict.parse(f.read())

# 频道 id → display-name（自动处理 dict / 多层结构）
def get_display_name(raw):
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        # 常见结构： {"#text": "江苏卫视"}
        if "#text" in raw:
            return raw["#text"]
        # 多语言结构： {"lang": "zh", "text": "江苏卫视"}
        if "text" in raw:
            return raw["text"]
        # 兜底：取第一个值
        return list(raw.values())[0]
    return str(raw)

channel_name = {}
for c in data["tv"]["channel"]:
    cid = c["@id"]
    raw_name = c["display-name"]
    name = get_display_name(raw_name)
    channel_name[cid] = name

epg = {}

# 节目单：按 display-name + 日期 分组
for p in data["tv"]["programme"]:
    cid = p["@channel"]
    ch_name = channel_name.get(cid, cid)  # 始终是字符串

    start = p["@start"]
    date = start[:8]          # YYYYMMDD
    time = start[8:12]        # HHMM

    title = p["title"]

    epg.setdefault(ch_name, {}).setdefault(date, []).append({
        "time": time[:2] + ":" + time[2:],
        "title": title
    })

# 写入 epg.json
os.makedirs("epg", exist_ok=True)
with open("epg/epg.json", "w", encoding="utf-8") as f:
    json.dump(epg, f, ensure_ascii=False, indent=2)

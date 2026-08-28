import xmltodict, json, os

with open("e.xml", encoding="utf-8") as f:
    data = xmltodict.parse(f.read())

# 统一把 dict 的 title / display-name 转成字符串
def normalize_text(raw):
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        # 常见格式 {"#text": "xxx"}
        if "#text" in raw:
            return raw["#text"]
        # {"text": "xxx"}
        if "text" in raw:
            return raw["text"]
        # 兜底：取第一个值
        return list(raw.values())[0]
    return str(raw)

# 频道 id → display-name
channel_name = {}
for c in data["tv"]["channel"]:
    cid = c["@id"]
    raw_name = c["display-name"]
    name = normalize_text(raw_name)
    channel_name[cid] = name

epg = {}

# 节目单
for p in data["tv"]["programme"]:
    cid = p["@channel"]
    ch_name = channel_name.get(cid, cid)

    start = p["@start"]
    date = start[:8]
    time = start[8:12]

    raw_title = p["title"]
    title = normalize_text(raw_title)

    epg.setdefault(ch_name, {}).setdefault(date, []).append({
        "time": time[:2] + ":" + time[2:],
        "title": title
    })

# 写入 epg.json
os.makedirs("epg", exist_ok=True)
with open("epg/epg.json", "w", encoding="utf-8") as f:
    json.dump(epg, f, ensure_ascii=False, indent=2)

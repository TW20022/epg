import xmltodict, json, os

with open("e.xml", encoding="utf-8") as f:
    data = xmltodict.parse(f.read())

# 统一把 dict 的 title / display-name 转成字符串
def normalize_text(raw):
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        if "#text" in raw:
            return raw["#text"]
        if "text" in raw:
            return raw["text"]
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
    date = start[:8]  # YYYYMMDD
    time = start[8:12]  # HHMM

    raw_title = p["title"]
    title = normalize_text(raw_title)

    day_list = epg.setdefault(ch_name, {}).setdefault(date, [])
    start_fmt = time[:2] + ":" + time[2:]

    # 去重：同一时间点只保留一条节目
    if not any(item["start"] == start_fmt for item in day_list):
        day_list.append({
            "start": start_fmt,
            "title": title
        })

# 自动计算 end 字段
for ch in epg:
    for date in epg[ch]:
        items = epg[ch][date]
        items.sort(key=lambda x: x["start"])

        for i in range(len(items)):
            if i < len(items) - 1:
                items[i]["end"] = items[i+1]["start"]
            else:
                items[i]["end"] = "00:00"  # 最后一条默认到午夜

# 写入 epg.json
os.makedirs("epg", exist_ok=True)
with open("epg/epg.json", "w", encoding="utf-8") as f:
    json.dump(epg, f, ensure_ascii=False, indent=2)

import xmltodict, json, os

with open("e.xml", encoding="utf-8") as f:
    data = xmltodict.parse(f.read())

# 频道 id → display-name
channel_name = {}
for c in data["tv"]["channel"]:
    cid = c["@id"]
    name = c["display-name"]
    channel_name[cid] = name

epg = {}

# 节目单：按 display-name + 日期 分组
for p in data["tv"]["programme"]:
    cid = p["@channel"]
    ch_name = channel_name.get(cid, cid)

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

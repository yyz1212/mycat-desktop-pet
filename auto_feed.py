"""
自动喂食脚本 - 每次执行时给 安安踩奶 补满饱食度
"""
import json

PET_DATA = "/Users/yangyunzhe/DyberPet/data/pet_data.json"

def feed():
    with open(PET_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "安安踩奶" in data:
        data["安安踩奶"]["HP"] = 200
        data["安安踩奶"]["HP_tier"] = 3
        with open(PET_DATA, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("已喂食 安安踩奶，饱食度已满")
    else:
        print("未找到 安安踩奶")

if __name__ == "__main__":
    feed()

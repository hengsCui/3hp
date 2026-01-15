import os

print("🔍 正在全盘扫描，寻找第 389 行有反斜杠的 _chemicals.py ...")

target_file = "_chemicals.py"
found = False

# 遍历所有文件夹
for root, dirs, files in os.walk("."):
    if target_file in files:
        full_path = os.path.join(root, target_file)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

                # 报错明确说是第 389 行，所以文件必须够长
                if len(lines) >= 389:
                    # 获取第 389 行的代码 (索引是388)
                    target_line = lines[388]

                    # 核心特征：这一行里同时有 'f' (f-string) 和 '\' (反斜杠)
                    if ("f\"" in target_line or "f'" in target_line) and "\\" in target_line:
                        print("\n" + "🔥" * 20)
                        print("🚨 终于抓到了！凶手就是它！")
                        print(f"📂 绝对路径: {full_path}")
                        print(f"❌ 第 389 行代码: {target_line.strip()}")
                        print("🔥" * 20 + "\n")
                        found = True
        except:
            pass

if not found:
    print("❌ 奇怪，还没找到。请确保你在 Bioindustrial-Park-master 根目录下运行。")
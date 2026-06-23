#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信群聊/私聊每日摘要 - 通用版
通过 wechat-cli 读取微信聊天记录，生成每日摘要。

功能：
  --setup          交互式配置向导
  --list-groups   列出所有群聊
  --list-contacts 列出所有联系人
  --mode all      监控所有群聊
  --mode specific 只监控配置文件中指定的群聊
  --mode discover 自动发现包含核心联系人的群聊（默认）
"""

import json
import os
import re
import subprocess
import datetime
import sys
import time
import argparse

# 强制 UTF-8 输出，避免 GBK 编码错误
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.yaml")
CONFIG_JSON = os.path.join(SCRIPT_DIR, "config_v2.json")  # 兼容旧版
KEY_FILE = os.path.join(os.path.expanduser("~"), ".wechat-cli", "all_keys.json")

# ── 默认配置 ────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "wechat_cli": "wechat-cli",  # 命令名或完整路径
    "output_dir": "summaries",
    "summary_hours": 24,
    "summary_mode": "rule",  # "rule" 或 "ollama"
    "ollama_model": "qwen2:7b",
    "max_messages_per_group": 500,
    "auto_discover": True,  # 是否自动发现含核心联系人的群

    # 群聊监控模式: "discover"(自动发现) | "all"(所有群) | "specific"(指定群名)
    "group_monitor_mode": "discover",

    # 指定监控的群名（mode=specific 时使用）
    "groups": [],

    # 核心联系人：用于自动发现群聊，以及私聊监控
    # 格式: [{"name": "显示名", "aliases": ["别名1", "别名2"]}, ...]
    "core_contacts": [],

    # 私聊监控模式: "core"(核心联系人) | "all"(所有私聊) | "specific"(指定联系人)
    "private_chat_mode": "core",

    # 指定监控的私聊联系人（mode=specific 时使用）
    "private_contacts": [],

    # 排除关键词：群名包含这些词的不纳入监控
    "exclude_keywords": [
        "好物", "分享群", "种草", "拼拼", "闲置", "二手",
        "购物", "团购", "优惠券", "红包", "外卖",
        "宠物", "撸猫", "遛狗", "游戏", "开黑",
        "相亲", "交友", "八卦",
    ],

    # 项目跟进配置（可选）
    "project_tracking": {
        "enabled": False,
        "projects": [],
    },
}


# ── 配置加载与保存 ───────────────────────────────────────────────────────────────

def load_config() -> dict:
    """加载配置文件，不存在则创建默认配置"""
    # 优先使用 YAML 格式
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            if HAS_YAML:
                cfg = yaml.safe_load(f) or {}
            else:
                # 没有 yaml 模块，尝试手动解析简单结构（兜底）
                print("[!] 未安装 PyYAML，使用 JSON 格式配置")
                return _load_json_config()
        # 合并默认值
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg

    # 兼容旧版 JSON 配置
    if os.path.exists(CONFIG_JSON):
        return _load_json_config()

    # 创建默认配置
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def _load_json_config() -> dict:
    with open(CONFIG_JSON, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg: dict):
    """保存配置到 YAML 文件"""
    os.makedirs(os.path.dirname(CONFIG_FILE) or ".", exist_ok=True)
    if HAS_YAML:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    else:
        # 没有 yaml 模块，保存为 JSON
        with open(CONFIG_JSON, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[+] 配置已保存：{CONFIG_FILE if HAS_YAML else CONFIG_JSON}")


# ── 交互式配置向导 ─────────────────────────────────────────────────────────────

def run_setup_wizard():
    """交互式配置向导"""
    print("\n" + "=" * 60)
    print(" 微信聊天摘要工具 - 初始化配置向导")
    print("=" * 60)

    cfg = load_config()

    # 1. wechat-cli 路径
    print("\n[1/5] wechat-cli 配置")
    print("    请确保已安装 wechat-cli（需要微信 PC 版正在运行）")
    current = cfg.get("wechat_cli", "wechat-cli")
    val = input(f"    wechat-cli 命令或路径 [{current}]: ").strip()
    if val:
        cfg["wechat_cli"] = val

    # 2. 群聊监控模式
    print("\n[2/5] 群聊监控模式")
    print("    1) discover - 自动发现含核心联系人的群（推荐）")
    print("    2) all       - 监控所有群聊")
    print("    3) specific - 只监控指定的群聊")
    mode = input("    请选择 [1/2/3, 默认=1]: ").strip() or "1"
    mode_map = {"1": "discover", "2": "all", "3": "specific"}
    cfg["group_monitor_mode"] = mode_map.get(mode, "discover")
    cfg["auto_discover"] = (cfg["group_monitor_mode"] == "discover")

    if cfg["group_monitor_mode"] == "specific":
        print("    请输入要监控的群名，每行一个，空行结束：")
        groups = []
        while True:
            line = input("    > ").strip()
            if not line:
                break
            groups.append(line)
        cfg["groups"] = groups

    # 3. 核心联系人配置
    print("\n[3/5] 核心联系人配置（用于自动发现群聊 + 私聊监控）")
    print("    请输入核心联系人，每行一个，空行结束。")
    print("    格式：显示名,别名1,别名2 （别名可选，用于精确匹配）")
    contacts = []
    while True:
        line = input("    > ").strip()
        if not line:
            break
        parts = [p.strip() for p in line.split(",")]
        contacts.append({"name": parts[0], "aliases": parts})
    if not contacts:
        contacts = cfg.get("core_contacts", [])
    cfg["core_contacts"] = contacts

    # 4. 私聊监控模式
    print("\n[4/5] 私聊监控模式")
    print("    1) core     - 监控核心联系人的私聊（推荐）")
    print("    2) specific - 监控指定的联系人")
    print("    3) all      - 监控所有私聊（消息量可能很大）")
    mode = input("    请选择 [1/2/3, 默认=1]: ").strip() or "1"
    private_mode_map = {"1": "core", "2": "specific", "3": "all"}
    cfg["private_chat_mode"] = private_mode_map.get(mode, "core")

    if cfg["private_chat_mode"] == "specific":
        print("    请输入要监控的联系人名称，每行一个，空行结束：")
        contacts = []
        while True:
            line = input("    > ").strip()
            if not line:
                break
            contacts.append(line)
        cfg["private_contacts"] = contacts

    # 5. 摘要模式
    print("\n[5/5] 摘要生成模式")
    print("    1) rule   - 规则模式（快速，无需额外依赖）")
    print("    2) ollama - AI 模式（需要安装 Ollama）")
    mode = input("    请选择 [1/2, 默认=1]: ").strip() or "1"
    cfg["summary_mode"] = "rule" if mode == "1" else "ollama"

    save_config(cfg)

    print("\n✅ 配置完成！")
    print(f"   配置文件：{CONFIG_FILE if HAS_YAML else CONFIG_JSON}")
    print(f"    今后可随时编辑配置文件，或重新运行 --setup 修改。")
    sys.exit(0)


def run_noninteractive_setup(args):
    """非交互式配置（供 AI 自动调用）"""
    print("\n" + "=" * 60)
    print(" 微信聊天摘要工具 - 自动配置（非交互式）")
    print("=" * 60)

    cfg = load_config()

    # 1. wechat-cli 路径
    if args.wechat_cli_path:
        cfg["wechat_cli"] = args.wechat_cli_path
        print(f"  [1/5] wechat-cli 路径：{args.wechat_cli_path}")

    # 2. 群聊监控模式
    if args.group_mode:
        cfg["group_monitor_mode"] = args.group_mode
        cfg["auto_discover"] = (args.group_mode == "discover")
        print(f"  [2/5] 群聊监控模式：{args.group_mode}")

    if args.groups:
        cfg["groups"] = args.groups
        print(f"        指定群聊：{args.groups}")

    # 3. 核心联系人
    if args.core_contacts:
        cfg["core_contacts"] = contacts = parse_core_contacts_arg(args.core_contacts)
        print(f"  [3/5] 核心联系人：{len(contacts)} 人")
        for c in contacts:
            print(f"        - {c['name']} (别名: {c['aliases']})")

    # 4. 私聊监控模式
    if args.private_mode:
        cfg["private_chat_mode"] = args.private_mode
        print(f"  [4/5] 私聊监控模式：{args.private_mode}")

    if args.private_contacts:
        cfg["private_contacts"] = args.private_contacts
        print(f"        指定私聊：{args.private_contacts}")

    # 5. 摘要模式
    if args.summary_mode:
        cfg["summary_mode"] = args.summary_mode
        print(f"  [5/5] 摘要模式：{args.summary_mode}")

    save_config(cfg)
    print("\n[OK] 配置完成！")
    sys.exit(0)


def parse_core_contacts_arg(raw: list) -> list:
    """解析 --core-contacts 参数
    格式：name:alias1:alias2  name:alias1 ...
    例如：--core-contacts 张三 李四:产品组李四 王五:王五_技术:老王
    """
    contacts = []
    for item in raw:
        parts = [p.strip() for p in item.split(":")]
        contacts.append({"name": parts[0], "aliases": parts})
    return contacts


# ── wechat-cli 调用 ────────────────────────────────────────────────────────────

def run_cli(cfg: dict, args: list) -> dict:
    """调用 wechat-cli，返回解析后的 JSON dict。失败抛异常。"""
    cmd = [cfg["wechat_cli"]] + args
    env = os.environ.copy()
    env["PYTHONUTF8"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"wechat-cli 执行失败 (exit={result.returncode}):\n"
            f"  命令: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    raw = result.stdout.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 尝试提取 JSON 部分
        first_brace = raw.find("{")
        if first_brace >= 0:
            try:
                return json.loads(raw[first_brace:])
            except json.JSONDecodeError:
                pass
        last_brace = raw.rfind("\n}")
        if last_brace > 0:
            try:
                return json.loads(raw[last_brace + 1:])
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"wechat-cli 输出无法解析为 JSON：\n{raw[:500]}")


def check_initialized() -> bool:
    return os.path.exists(KEY_FILE)


# ── 群聊/联系人列表 ──────────────────────────────────────────────────────────

def list_groups(cfg: dict):
    """列出所有群聊"""
    print("\n[扫描] 正在获取群聊列表...")
    data = run_cli(cfg, ["sessions", "--format", "json", "--limit", "500"])
    sessions = data if isinstance(data, list) else data.get("sessions", [])
    groups = [s for s in sessions if s.get("is_group")]
    print(f"\n共发现 {len(groups)} 个群聊：\n")
    for i, g in enumerate(groups, 1):
        name = g.get("chat", "") or g.get("username", "")
        username = g.get("username", "")
        print(f"  {i:3d}. {name}")
        print(f"       ID: {username}")
    print(f"\n总计：{len(groups)} 个群聊")
    return groups


def list_contacts(cfg: dict):
    """列出所有联系人"""
    print("\n[扫描] 正在获取联系人列表...")
    data = run_cli(cfg, ["contacts", "--format", "json"])
    contacts = data if isinstance(data, list) else data.get("contacts", [])
    print(f"\n共发现 {len(contacts)} 个联系人：\n")
    for i, c in enumerate(contacts, 1):
        name = c.get("display_name") or c.get("remark") or c.get("nick_name", "")
        username = c.get("username", "")
        print(f"  {i:3d}. {name}")
        print(f"       ID: {username}")
    print(f"\n总计：{len(contacts)} 个联系人")
    return contacts


# ── 核心联系人匹配 ─────────────────────────────────────────────────────────────

def get_core_contacts_map(cfg: dict) -> dict:
    """返回 {显示名: [别名列表]} 格式的 core_contacts"""
    result = {}
    for item in cfg.get("core_contacts", []):
        if isinstance(item, dict):
            result[item["name"]] = item.get("aliases", [item["name"]])
        elif isinstance(item, str):
            result[item] = [item]
    return result


def is_core_contact_member(member: dict, core_map: dict) -> str | None:
    """判断成员是否为核心联系人，返回联系人姓名"""
    display = member.get("display_name", "")
    remark = member.get("remark", "")
    nick = member.get("nick_name", "")
    for name, aliases in core_map.items():
        for alias in aliases:
            if display == alias or remark == alias or nick == alias:
                return name
    return None


# ── 群聊发现 ──────────────────────────────────────────────────────────────────

def discover_groups(cfg: dict, core_map: dict) -> tuple:
    """
    根据配置模式发现需要监控的群聊。
    返回 (target_groups, new_groups, contacts_in_groups)
    """
    mode = cfg.get("group_monitor_mode", "discover")
    exclude_kw = cfg.get("exclude_keywords", [])

    if mode == "all":
        # 监控所有群
        print("\n[扫描] 获取所有群聊...")
        data = run_cli(cfg, ["sessions", "--format", "json", "--limit", "500"])
        sessions = data if isinstance(data, list) else data.get("sessions", [])
        all_groups = [s.get("chat", "") or s.get("username", "") for s in sessions if s.get("is_group")]
        # 过滤排除关键词
        target_groups = [g for g in all_groups if g and not any(kw in g for kw in exclude_kw)]
        print(f"[扫描结果] 监控所有群聊：{len(target_groups)} 个")
        return target_groups, [], {}

    elif mode == "specific":
        # 使用配置的指定群名
        target_groups = cfg.get("groups", [])
        print(f"[配置] 监控指定群聊：{len(target_groups)} 个")
        return target_groups, [], {}

    else:  # discover 模式
        return discover_by_core_contacts(cfg, core_map)


def discover_by_core_contacts(cfg: dict, core_map: dict) -> tuple:
    """扫描所有群，找出包含核心联系人的群"""
    print("\n[扫描] 正在扫描所有群聊，查找核心联系人...")
    data = run_cli(cfg, ["sessions", "--format", "json", "--limit", "500"])
    sessions = data if isinstance(data, list) else data.get("sessions", [])
    all_groups = [{"name": s.get("chat", "") or s.get("username", ""),
                   "username": s.get("username", "")} for s in sessions if s.get("is_group")]

    static_groups = cfg.get("groups", [])
    existing_names = set(static_groups)
    relevant = []
    new_found = []
    contacts_in_groups = {}

    exclude_kw = cfg.get("exclude_keywords", [])
    print(f"  共 {len(all_groups)} 个群聊，正在检查成员...")

    for g in all_groups:
        gname = g["name"]
        if not gname:
            continue
        if any(kw in gname for kw in exclude_kw):
            continue
        try:
            mdata = run_cli(cfg, ["members", gname, "--format", "json"])
            members = mdata.get("members", [])
        except Exception as e:
            print(f"  [!] 获取群成员失败：{gname} ({e})")
            continue

        found_contacts = []
        for m in members:
            contact = is_core_contact_member(m, core_map)
            if contact and contact not in found_contacts:
                found_contacts.append(contact)

        if found_contacts:
            relevant.append(gname)
            contacts_in_groups[gname] = found_contacts
            if gname not in existing_names:
                new_found.append(gname)
            status = "🆕 新群" if gname not in existing_names else "  "
            print(f"  [{status}] {gname} → {', '.join(found_contacts)}")
        time.sleep(0.3)

    print(f"\n[扫描结果] 相关群聊：{len(relevant)} 个（新发现：{len(new_found)} 个）")
    return relevant, new_found, contacts_in_groups


# ── 消息解析 ──────────────────────────────────────────────────────────────────

_MSG_RE = re.compile(r"^\[([^\]]+)\]\s*(.+?:\s*)?(.*)")

def parse_messages(lines: list) -> list:
    parsed = []
    for line in lines:
        m = _MSG_RE.match(line.strip())
        if not m:
            continue
        time_str = m.group(1)
        sender_raw = (m.group(2) or "").strip()
        text = (m.group(3) or "").strip()
        sender = sender_raw[:-1].strip() if sender_raw.endswith(":") else sender_raw
        msg_type = "text"
        if text.startswith("[图片]"):
            msg_type = "image"
        elif text.startswith("[表情]"):
            msg_type = "sticker"
        elif text.startswith("[文件]"):
            msg_type = "file"
        elif text.startswith("[链接]"):
            msg_type = "link"
        elif text.startswith("[视频]"):
            msg_type = "video"
        elif text.startswith("[语音]"):
            msg_type = "voice"
        elif text.startswith("[通话]"):
            msg_type = "call"
        elif text.startswith("[系统]") or text.startswith("[撤回]"):
            msg_type = "system"
        parsed.append({"time": time_str, "sender": sender, "text": text, "type": msg_type})
    return parsed


# ── 摘要生成（规则模式）───────────────────────────────────────────────────────

import collections

def parse_time_str(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")


def generate_summary_rule(group_name: str, messages: list, summary_hours: int,
                           today: str = None, is_today: bool = True) -> str:
    now = datetime.datetime.now()

    # 确定统计时段显示
    if is_today:
        period_label = f"过去 {summary_hours} 小时"
    else:
        period_label = f"{today} 全天"

    if not messages:
        return f"# {group_name} 每日摘要 ({period_label})\n\n（{period_label}无消息）\n"

    if is_today:
        cutoff = now - datetime.timedelta(hours=summary_hours)
    else:
        # 历史日期：当天 00:00 作为阈值，消息都已由 wechat-cli 过滤，无需二次过滤
        cutoff = datetime.datetime.strptime(f"{today} 00:00", "%Y-%m-%d %H:%M")

    active = [m for m in messages if parse_time_str(m["time"]) >= cutoff]
    if not active:
        active = messages

    senders = collections.Counter(m["sender"] for m in active if m["sender"])
    type_counts = collections.Counter(m["type"] for m in active)
    hours = collections.Counter(
        datetime.datetime.strptime(m["time"], "%Y-%m-%d %H:%M").hour
        for m in active
    )

    lines = []
    lines.append(f"# {group_name} 每日摘要")
    lines.append(f"生成时间：{now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"统计时段：{period_label}")
    lines.append(f"消息总数：**{len(active)}** 条\n")

    lines.append("## 活跃度统计")
    lines.append(f"- 活跃发言人（Top 5）：")
    for name, cnt in senders.most_common(5):
        lines.append(f"  - {name}：{cnt} 条")
    lines.append(f"- 消息类型分布：{dict(type_counts)}")
    if hours:
        peak = hours.most_common(1)[0]
        lines.append(f"- 最活跃时段：{peak[0]:02d}:00～{peak[0]:02d}:59（{peak[1]} 条）")
    lines.append("")

    lines.append("## 近期消息摘录（最新 30 条）")
    for m in active[-30:]:
        sender_tag = f"{m['sender']}：" if m["sender"] else ""
        lines.append(f"- [{m['time']}] {sender_tag}{m['text'][:120]}")
    lines.append("")

    return "\n".join(lines)


def generate_summary_ollama(group_name: str, messages: list, model: str) -> str:
    if not messages:
        return f"# {group_name} 每日摘要\n\n（无消息）\n"

    now = datetime.datetime.now()
    msg_text = "\n".join(
        f"[{m['time']}] {m['sender'] or '未知'}：{m['text']}"
        for m in messages[-200:]
    )
    prompt = (
        f"以下是微信群「{group_name}」过去 24 小时的聊天记录，"
        f"请生成一份简洁的每日摘要，包括：重要话题、关键决定、待办事项。\n\n"
        f"{msg_text}\n\n摘要："
    )

    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        ai_text = result.stdout.strip()
        if not ai_text:
            ai_text = "（Ollama 未返回内容，请检查 ollama 是否正常运行）"
    except FileNotFoundError:
        ai_text = "（未检测到 ollama 命令，请先安装 Ollama：https://ollama.com）"
    except subprocess.TimeoutExpired:
        ai_text = "（Ollama 响应超时，请稍后重试）"

    return f"# {group_name} 每日摘要（AI）\n\n生成时间：{now.strftime('%Y-%m-%d %H:%M')}\n\n{ai_text}\n"


# ── 处理单个聊天 ──────────────────────────────────────────────────────────────

def process_chat(cfg: dict, chat_name: str, chat_type: str, output_dir: str,
                  summary_hours: int, mode: str, today: str) -> str | None:
    """处理单个群聊或私聊，返回生成的摘要文件路径"""
    type_label = "群聊" if chat_type == "group" else "私聊"
    print(f"\n{'─' * 60}")
    print(f"处理{type_label}：{chat_name}")
    print(f"{'─' * 60}")

    # 区分"今天"和"指定历史日期"：历史日期取全天 00:00-23:59
    dt_today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    is_today = (today == dt_today_str)

    if is_today:
        start_dt = datetime.datetime.now() - datetime.timedelta(hours=summary_hours)
        start_str = start_dt.strftime("%Y-%m-%d %H:%M")
        end_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    else:
        start_str = f"{today} 00:00"
        end_str = f"{today} 23:59"

    print(f"    时间范围：{start_str} ~ {end_str}")

    try:
        data = run_cli(cfg, [
            "history", chat_name,
            "--format", "json",
            "--start-time", start_str,
            "--end-time", end_str,
            "--limit", str(cfg.get("max_messages_per_group", 500)),
        ])
    except RuntimeError as e:
        print(f"[!] 获取消息失败：{e}")
        return None

    raw_messages = data.get("messages", [])
    print(f"    获取消息：{len(raw_messages)} 条")

    parsed = parse_messages(raw_messages)
    print(f"    解析成功：{len(parsed)} 条")

    if mode == "ollama":
        summary = generate_summary_ollama(chat_name, parsed, cfg.get("ollama_model", "qwen2:7b"))
    else:
        summary = generate_summary_rule(chat_name, parsed, summary_hours, today, is_today)

    safe_name = re.sub(r'[\\/*?:"<>|]', "_", chat_name)[:50]
    out_path = os.path.join(output_dir, f"{today}_{safe_name}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"    摘要已保存：{os.path.basename(out_path)}")
    return out_path


# ── 项目跟进对照（可选）───────────────────────────────────────────────────────

def generate_project_tracking_report(cfg: dict, output_dir: str, today: str) -> str | None:
    """根据配置中的 project_tracking 生成项目跟进报告"""
    pt_cfg = cfg.get("project_tracking", {})
    if not pt_cfg.get("enabled"):
        return None

    projects = pt_cfg.get("projects", [])
    if not projects:
        return None

    print("\n" + "=" * 60)
    print("📌 项目跟进对照")
    print("=" * 60)

    summaries: dict[str, str] = {}
    pattern = re.compile(rf"^{re.escape(today)}_(.+)\.md$")
    exclude_suffixes = {"项目跟进对照", "scan_result"}
    for fname in os.listdir(output_dir):
        m = pattern.match(fname)
        if not m:
            continue
        group_hint = m.group(1)
        if group_hint in exclude_suffixes:
            continue
        fpath = os.path.join(output_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                summaries[group_hint] = f.read()
        except Exception:
            pass

    if not summaries:
        print(f"  [!] 未找到 {today} 的摘要文件，跳过项目跟进报告。")
        return None

    print(f"  已加载 {len(summaries)} 份摘要文件")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"# 项目跟进对照报告")
    lines.append(f"**生成时间：** {now_str}  ")
    lines.append(f"**数据日期：** {today}  ")
    lines.append(f"**摘要来源：** {len(summaries)} 个群聊/私聊\n")
    lines.append("---\n")

    for proj in projects:
        lines.append(f"## {proj.get('name', '未命名项目')}")
        keywords = proj.get("keywords", [])
        related_groups = proj.get("related_groups", [])

        hits = []
        for rg in related_groups:
            for hint, content in summaries.items():
                if rg in hint or hint in rg:
                    relevant_lines = _extract_relevant_lines(content, keywords)
                    if relevant_lines:
                        hits.append((hint, relevant_lines))
                    elif "无消息" not in content:
                        last = _extract_last_lines(content, n=5)
                        if last:
                            hits.append((hint, last))

        already_hints = {h for h, _ in hits}
        for hint, content in summaries.items():
            if hint in already_hints:
                continue
            relevant_lines = _extract_relevant_lines(content, keywords)
            if relevant_lines:
                hits.append((hint, relevant_lines))

        if hits:
            for hint, snippet_lines in hits:
                lines.append(f"\n**来源：** `{hint}`")
                for sl in snippet_lines:
                    lines.append(f"> {sl}")
        else:
            lines.append("\n> ⚪ 今日无相关动态")

        lines.append("")

    lines.append("---")
    lines.append(f"*由 wechat-daily-summary 自动生成 · {now_str}*")

    report_content = "\n".join(lines)
    report_path = os.path.join(output_dir, f"{today}_项目跟进对照.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"  ✅ 项目跟进报告已保存：{report_path}")
    return report_path


def _extract_relevant_lines(content: str, keywords: list) -> list:
    result = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if any(kw.lower() in stripped.lower() for kw in keywords):
            if stripped not in result:
                result.append(stripped)
        if len(result) >= 8:
            break
    return result


def _extract_last_lines(content: str, n: int = 5) -> list:
    msg_lines = [l.strip() for l in content.splitlines() if l.strip().startswith("- [")]
    return msg_lines[-n:] if msg_lines else []


# ── 日期范围工具 ───────────────────────────────────────────────────────────────

def get_date_range(start_str: str, end_str: str) -> list[str]:
    """返回从 start 到 end（含）的日期列表"""
    start = datetime.datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.datetime.strptime(end_str, "%Y-%m-%d")
    if start > end:
        start, end = end, start
    days = []
    current = start
    while current <= end:
        days.append(current.strftime("%Y-%m-%d"))
        current += datetime.timedelta(days=1)
    return days


def get_weekday_cn(date_str: str) -> str:
    """返回中文星期"""
    wd = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return wd[dt.weekday()]


# ── 聚合摘要生成（日期范围模式）────────────────────────────────────────────────

def generate_aggregated_summary(chat_name: str, all_messages: list,
                                 start_date: str, end_date: str) -> str:
    """为单个聊天生成跨日期聚合摘要"""
    now = datetime.datetime.now()
    days_count = len(get_date_range(start_date, end_date))

    if not all_messages:
        return (f"# {chat_name} 聚合摘要\n\n"
                f"统计时段：{start_date} ~ {end_date}（{days_count} 天）\n\n"
                f"（此期间无消息）\n")

    # 按日期分组
    by_date: dict[str, list] = {}
    for m in all_messages:
        t = m.get("time", "")
        date_key = t[:10] if t else "未知"
        by_date.setdefault(date_key, []).append(m)

    # 统计
    senders = collections.Counter(m.get("sender", "") for m in all_messages if m.get("sender"))
    text_all = " ".join(m.get("text", "") for m in all_messages)

    # 简易关键词提取（高频 2-6 字词，过滤停用词）
    stopwords = {
        "如果", "因为", "所以", "这个", "那个", "我们", "他们", "你们", "就是", "已经",
        "还是", "可以", "不是", "自己", "什么", "没有", "一个", "一下", "怎么", "知道",
        "现在", "然后", "但是", "不过", "还有", "可能", "应该", "觉得", "比较", "非常",
    }
    kw_counter: dict[str, int] = {}
    for seg in re.findall(r"[\u4e00-\u9fff\w]{2,6}", text_all):
        if seg not in stopwords:
            kw_counter[seg] = kw_counter.get(seg, 0) + 1
    top_keywords = sorted(kw_counter.items(), key=lambda x: -x[1])[:10]

    total_count = len(all_messages)
    active_days = len(by_date)

    lines = []
    lines.append(f"# {chat_name} 聚合摘要")
    lines.append(f"统计时段：{start_date} ~ {end_date}（{days_count} 天）")
    lines.append(f"生成时间：{now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"消息总数：**{total_count}** 条 | 有消息天数：**{active_days}**/{days_count}")
    lines.append("")

    # 日活跃度趋势
    lines.append("## 📊 日活跃度趋势")
    lines.append("| 日期 | 消息数 | Top 发言人 |")
    lines.append("|------|--------|-----------|")
    for d in get_date_range(start_date, end_date):
        msgs = by_date.get(d, [])
        ds = collections.Counter(m.get("sender", "") for m in msgs if m.get("sender"))
        top_s = ", ".join(f"{s}({c})" for s, c in ds.most_common(2))
        lines.append(f"| {d} {get_weekday_cn(d)} | {len(msgs)} | {top_s or '-'} |")
    lines.append("")

    # 活跃发言人
    if senders:
        lines.append("## 👤 活跃发言人")
        for name, cnt in senders.most_common(8):
            lines.append(f"- **{name}**：{cnt} 条")
        lines.append("")

    # 关键词
    if top_keywords:
        lines.append("## 🔑 高频关键词")
        kw_parts = [f"**{kw}**({cnt})" for kw, cnt in top_keywords if cnt >= 2]
        if kw_parts:
            lines.append(" · ".join(kw_parts))
        lines.append("")

    # 时间线（按天，每天最新 15 条）
    lines.append("## 📅 时间线")
    for d in get_date_range(start_date, end_date):
        msgs = by_date.get(d, [])
        if not msgs:
            continue
        lines.append(f"### {d} {get_weekday_cn(d)}（{len(msgs)} 条）")
        for m in msgs[-15:]:
            t = m.get("time", "")[11:16] if m.get("time") else "??:??"
            sender = m.get("sender", "") or "?"
            text = m.get("text", "")[:150]
            lines.append(f"- [{t}] **{sender}**：{text}")
        lines.append("")

    # 整体总结提示
    lines.append("## 💡 整体总结")
    lines.append(f"> 本周期 {chat_name} 共 {total_count} 条消息，覆盖 {active_days} 天。")
    if top_keywords:
        top3 = [kw for kw, _ in top_keywords[:3]]
        lines.append(f"> 核心话题：{'、'.join(top3)}。")
    if senders:
        lines.append(f"> 最活跃：{senders.most_common(1)[0][0]}（{senders.most_common(1)[0][1]} 条）。")
    lines.append("")

    return "\n".join(lines)


def generate_master_report(chat_summaries: dict[str, dict],
                            start_date: str, end_date: str) -> str:
    """生成跨群聊的聚合主报告"""
    now = datetime.datetime.now()
    days = get_date_range(start_date, end_date)
    days_count = len(days)

    total_msgs = 0
    total_groups = 0
    total_private = 0
    all_text = ""
    all_senders: collections.Counter = collections.Counter()

    for info in chat_summaries.values():
        msgs = info.get("messages", [])
        total_msgs += len(msgs)
        all_text += " " + " ".join(m.get("text", "") for m in msgs)
        all_senders.update(m.get("sender", "") for m in msgs if m.get("sender"))
        if info.get("type") == "group":
            total_groups += 1
        else:
            total_private += 1

    # 全局关键词
    stopwords = {
        "如果", "因为", "所以", "这个", "那个", "我们", "他们", "你们", "就是", "已经",
        "还是", "可以", "不是", "自己", "什么", "没有", "一个", "一下", "怎么", "知道",
        "现在", "然后", "但是", "不过", "还有", "可能", "应该", "觉得", "比较", "非常",
    }
    kw_counter: dict[str, int] = {}
    for seg in re.findall(r"[\u4e00-\u9fff\w]{2,6}", all_text):
        if seg not in stopwords:
            kw_counter[seg] = kw_counter.get(seg, 0) + 1
    global_kw = sorted(kw_counter.items(), key=lambda x: -x[1])[:15]

    # 按聊天活跃度排序
    chat_activity = []
    for name, info in chat_summaries.items():
        chat_activity.append((name, len(info.get("messages", [])), info.get("type", "")))
    chat_activity.sort(key=lambda x: -x[1])

    lines = []
    lines.append(f"# 📋 周期报告")
    lines.append(f"时段：{start_date} ~ {end_date}（{days_count} 天）")
    lines.append(f"生成：{now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## 概览")
    lines.append(f"- 监控群聊：**{total_groups}** 个 | 私聊：**{total_private}** 人")
    lines.append(f"- 消息总量：**{total_msgs}** 条")
    lines.append(f"- 参与人数：**{len(all_senders)}** 人")
    if global_kw:
        top5 = [f"**{k}**({c})" for k, c in global_kw[:5]]
        lines.append(f"- 热点话题：{' · '.join(top5)}")
    lines.append("")

    # 活跃度排行
    lines.append("## 🔥 聊天活跃度排行")
    lines.append("| 排名 | 聊天 | 类型 | 消息数 |")
    lines.append("|------|------|------|--------|")
    for i, (name, cnt, ctype) in enumerate(chat_activity[:20], 1):
        badge = "📱" if ctype == "contact" else "💬"
        lines.append(f"| {i} | {badge} {name} | {ctype} | {cnt} |")
    lines.append("")

    # 全局活跃人物
    if all_senders:
        lines.append("## 👤 全局活跃人物 (Top 10)")
        for name, cnt in all_senders.most_common(10):
            lines.append(f"- **{name}**：{cnt} 条")
        lines.append("")

    # 全局关键词
    if global_kw:
        lines.append("## 🔑 全局高频关键词")
        kw_parts = [f"**{kw}**({cnt})" for kw, cnt in global_kw if cnt >= 2]
        if kw_parts:
            lines.append(" · ".join(kw_parts))
        lines.append("")

    # 各聊天简要（可折叠）
    lines.append("## 📑 各群聊/私聊摘要")
    for name, cnt, ctype in chat_activity:
        badge = "📱" if ctype == "contact" else "💬"
        info = chat_summaries.get(name, {})
        lines.append(f"<details>")
        lines.append(f"<summary>{badge} <b>{name}</b> — {cnt} 条消息</summary>")
        lines.append("")
        lines.append(info.get("summary", "（无摘要）"))
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


# ── 日期范围模式主流程 ──────────────────────────────────────────────────────

def run_date_range(cfg: dict, start_date: str, end_date: str,
                    target_groups: list, target_contacts: list,
                    output_dir: str, new_groups: list = None,
                    contacts_in_groups: dict = None) -> str:
    """以聚合模式处理日期范围，返回主报告路径"""
    days = get_date_range(start_date, end_date)
    days_count = len(days)
    if days_count > 7:
        print(f"\n⚠️  日期跨度 {days_count} 天（超过 7 天），聚合摘要可能信息量较大。")
        print(f"    建议缩小范围以获更聚焦的摘要。")
        print(f"    继续执行...\n")

    all_chats = list(target_groups) + list(target_contacts)
    limit = cfg.get("max_messages_per_group", 500)

    # Phase 1: 按聊天累积所有日期的消息（自动去重）
    chat_messages: dict[str, list] = {}
    chat_types: dict[str, str] = {}
    seen_fingerprints: dict[str, set] = {}

    for gn in target_groups:
        chat_types[gn] = "group"
        chat_messages[gn] = []
        seen_fingerprints[gn] = set()
    for cn in target_contacts:
        chat_types[cn] = "contact"
        chat_messages[cn] = []
        seen_fingerprints[cn] = set()

    for di, date_str in enumerate(days):
        print(f"\n{'─' * 50}")
        print(f"  Day {di+1}/{days_count}: {date_str} {get_weekday_cn(date_str)}")
        print(f"{'─' * 50}")

        for chat_name in all_chats:
            type_label = "群" if chat_types[chat_name] == "group" else "私"
            try:
                data = run_cli(cfg, [
                    "history", chat_name,
                    "--format", "json",
                    "--start-time", f"{date_str} 00:00",
                    "--end-time", f"{date_str} 23:59",
                    "--limit", str(limit),
                ])
            except RuntimeError as e:
                print(f"  [{type_label}] {chat_name}: 获取失败 ({e})")
                continue

            raw = data.get("messages", [])
            parsed = parse_messages(raw)

            # 去重
            new_count = 0
            fp_set = seen_fingerprints[chat_name]
            for m in parsed:
                fp = (m.get("time", ""), m.get("sender", ""), m.get("text", "")[:80])
                if fp not in fp_set:
                    fp_set.add(fp)
                    chat_messages[chat_name].append(m)
                    new_count += 1

            if new_count > 0:
                print(f"  [{type_label}] {chat_name}: +{new_count}")
        time.sleep(0.3)

    # Phase 2: 生成聚合摘要
    print(f"\n{'=' * 50}")
    print(f"  生成聚合摘要...")
    print(f"{'=' * 50}")

    chat_summaries: dict[str, dict] = {}

    for chat_name in all_chats:
        msgs = chat_messages[chat_name]
        if not msgs:
            continue

        summary_text = generate_aggregated_summary(chat_name, msgs, start_date, end_date)
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", chat_name)[:50]
        out_path = os.path.join(output_dir, f"{start_date}_to_{end_date}_{safe_name}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        chat_summaries[chat_name] = {
            "type": chat_types[chat_name],
            "messages": msgs,
            "summary": summary_text,
        }

    print(f"  已生成 {len(chat_summaries)} 个聚合摘要")

    # Phase 3: 主报告
    master = generate_master_report(chat_summaries, start_date, end_date)
    master_path = os.path.join(output_dir, f"{start_date}_to_{end_date}_周期报告.md")
    with open(master_path, "w", encoding="utf-8") as f:
        f.write(master)
    print(f"  主报告: {os.path.basename(master_path)}")

    # 保存结果索引
    results = {
        "type": "date_range",
        "start_date": start_date,
        "end_date": end_date,
        "days": days_count,
        "groups": [{"name": n} for n in target_groups],
        "contacts": [{"name": n} for n in target_contacts],
        "new_groups": new_groups or [],
        "master_report": master_path,
    }
    result_path = os.path.join(output_dir, f"{start_date}_to_{end_date}_scan_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_msgs = sum(len(v["messages"]) for v in chat_summaries.values())
    print(f"\n  聚合完成！{days_count} 天 / {len(chat_summaries)} 个活跃聊天 / {total_msgs} 条消息")
    print(f"  → {master_path}")

    return master_path


# ── 主流程 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="微信群聊/私聊每日摘要 - 通用版")
    parser.add_argument("--setup", action="store_true", help="交互式配置向导")
    parser.add_argument("--list-groups", action="store_true", help="列出所有群聊")
    parser.add_argument("--list-contacts", action="store_true", help="列出所有联系人")
    parser.add_argument("--mode", type=str, default=None,
                        help="临时指定群聊监控模式: all / discover / specific")
    parser.add_argument("--date", type=str, default=None,
                        help="指定日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--date-range", type=str, default=None, nargs=2,
                        metavar=("START", "END"),
                        help="日期范围 YYYY-MM-DD YYYY-MM-DD（含首尾），生成聚合摘要")
    # 非交互式配置参数（供 AI 自动调用）
    parser.add_argument("--core-contacts", type=str, default=None, nargs="+",
                        help="核心联系人列表，空格分隔，可带别名用冒号: 张三 李四:李四_产品组")
    parser.add_argument("--group-mode", type=str, default=None,
                        choices=["discover", "all", "specific"],
                        help="群聊监控模式")
    parser.add_argument("--private-mode", type=str, default=None,
                        choices=["core", "all", "specific"],
                        help="私聊监控模式")
    parser.add_argument("--summary-mode", type=str, default=None,
                        choices=["rule", "ollama"],
                        help="摘要生成模式")
    parser.add_argument("--wechat-cli-path", type=str, default=None,
                        help="wechat-cli 命令路径")
    parser.add_argument("--groups", type=str, default=None, nargs="+",
                        help="指定监控的群名列表（--group-mode specific 时使用）")
    parser.add_argument("--private-contacts", type=str, default=None, nargs="+",
                        help="指定监控的私聊联系人（--private-mode specific 时使用）")
    args = parser.parse_args()

    # 检查 PyYAML
    if not HAS_YAML:
        print("[!] 建议安装 PyYAML：pip install pyyaml")
        print("    （当前使用 JSON 格式配置）\n")

    # 加载配置
    cfg = load_config()

    # --setup 模式
    if args.setup:
        # 如果提供了核心联系人参数，使用非交互式模式（供 AI 自动调用）
        if args.core_contacts:
            run_noninteractive_setup(args)
        else:
            run_setup_wizard()

    # --list-groups / --list-contacts 模式
    if args.list_groups:
        cfg_tmp = load_config()
        if not check_initialized():
            print("\n[!] wechat-cli 尚未初始化！请先运行：wechat-cli init")
            sys.exit(1)
        list_groups(cfg_tmp)
        sys.exit(0)

    if args.list_contacts:
        cfg_tmp = load_config()
        if not check_initialized():
            print("\n[!] wechat-cli 尚未初始化！请先运行：wechat-cli init")
            sys.exit(1)
        list_contacts(cfg_tmp)
        sys.exit(0)

    # 临时覆盖模式
    if args.mode:
        if args.mode not in ("all", "discover", "specific"):
            print(f"[!] 无效的 --mode 值：{args.mode}，请使用 all / discover / specific")
            sys.exit(1)
        cfg["group_monitor_mode"] = args.mode
        cfg["auto_discover"] = (args.mode == "discover")

    # 检查初始化
    if not check_initialized():
        print("\n[!] wechat-cli 尚未初始化！")
        print("    请先运行：wechat-cli init")
        print("    确保微信 PC 版正在运行且已登录。")
        print("    首次使用请运行：python run_daily_v3.py --setup")
        sys.exit(1)

    print("=" * 60)
    print("微信群聊/私聊每日摘要 - 通用版")
    print(f"启动：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"[+] wechat-cli 已初始化")

    # 确定日期
    today = args.date or os.environ.get("WECHAT_SUMMARY_DATE") or \
             datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"[+] 摘要目标日期：{today}")

    # 获取核心联系人映射
    core_map = get_core_contacts_map(cfg)

    # 第一步：确定需要监控的群聊
    print("\n" + "=" * 60)
    print("🔍 第一步：确定监控群聊")
    print("=" * 60)

    if cfg.get("group_monitor_mode") == "discover":
        # discover_by_core_contacts 返回 (relevant, new_found, contacts_in_groups)
        all_relevant, new_groups, contacts_in_groups = discover_groups(cfg, core_map)
        static_groups = cfg.get("groups", [])
        target_groups = list(dict.fromkeys(static_groups + all_relevant))
        if new_groups:
            print(f"\n🆕 发现 {len(new_groups)} 个新群聊：")
            for ng in new_groups:
                print(f"   - {ng}（成员：{', '.join(contacts_in_groups.get(ng, []))}）")
        print(f"\n📋 最终监控群聊：{len(target_groups)} 个")
    else:
        target_groups, new_groups, contacts_in_groups = discover_groups(cfg, core_map)
        print(f"\n📋 最终监控群聊：{len(target_groups)} 个")

    # 第二步：确定私聊联系人
    print("\n" + "=" * 60)
    print("📱 第二步：确定私聊联系人")
    print("=" * 60)

    private_mode = cfg.get("private_chat_mode", "core")
    if private_mode == "core":
        target_contacts = list(dict.fromkeys([c["name"] for c in cfg.get("core_contacts", [])]))
        print(f"[-] 私聊监控：核心联系人（{len(target_contacts)} 人）")
    elif private_mode == "specific":
        target_contacts = cfg.get("private_contacts", [])
        print(f"[-] 私聊监控：指定联系人（{len(target_contacts)} 人）")
    else:  # all
        print("[-] 私聊监控：所有联系人（可能需要较长时间）")
        data = run_cli(cfg, ["contacts", "--format", "json"])
        contacts = data if isinstance(data, list) else data.get("contacts", [])
        target_contacts = [c.get("display_name") or c.get("username", "") for c in contacts]
        target_contacts = [c for c in target_contacts if c]

    # 第三步：生成摘要
    os.makedirs(os.path.join(SCRIPT_DIR, cfg["output_dir"]), exist_ok=True)

    # ── 日期范围模式：聚合多日消息 ──
    if args.date_range:
        start_range, end_range = args.date_range
        print("\n" + "=" * 60)
        print(f"📅 聚合模式：{start_range} ~ {end_range}")
        print("=" * 60)
        run_date_range(cfg, start_range, end_range,
                        target_groups, target_contacts,
                        os.path.join(SCRIPT_DIR, cfg["output_dir"]),
                        new_groups if cfg.get("group_monitor_mode") == "discover" else [],
                        contacts_in_groups)
        print(f"\n✅ 全部完成！摘要目录：{cfg['output_dir']}/\n")
        return

    summary_hours = cfg.get("summary_hours", 24)
    mode = cfg.get("summary_mode", "rule")

    print("\n" + "=" * 60)
    print("📊 第三步：生成摘要")
    print("=" * 60)

    results = {"groups": [], "contacts": [], "new_groups": new_groups if cfg.get("group_monitor_mode") == "discover" else []}

    for group_name in target_groups:
        result_path = process_chat(cfg, group_name, "group",
                                   os.path.join(SCRIPT_DIR, cfg["output_dir"]),
                                   summary_hours, mode, today)
        if result_path:
            results["groups"].append({
                "name": group_name,
                "path": result_path,
                "is_new": group_name in (new_groups or []),
                "core_members": contacts_in_groups.get(group_name, []),
            })
        time.sleep(0.5)

    for contact_name in target_contacts:
        result_path = process_chat(cfg, contact_name, "contact",
                                   os.path.join(SCRIPT_DIR, cfg["output_dir"]),
                                   summary_hours, mode, today)
        if result_path:
            results["contacts"].append({
                "name": contact_name,
                "path": result_path,
            })
        time.sleep(0.5)

    # 第四步：输出扫描摘要
    print("\n" + "=" * 60)
    print("📋 执行摘要")
    print("=" * 60)
    print(f"处理群聊：{len(results['groups'])} 个")
    print(f"处理私聊：{len(results['contacts'])} 个")
    if results.get("new_groups"):
        print(f"🆕 新发现群聊：{len(results['new_groups'])} 个")
        for ng in results["new_groups"]:
            print(f"   - {ng}")

    scan_result_path = os.path.join(SCRIPT_DIR, cfg["output_dir"], f"{today}_scan_result.json")
    with open(scan_result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n扫描结果已保存：{scan_result_path}")

    print(f"\n✅ 全部完成！摘要目录：{cfg['output_dir']}/\n")

    # 第五步：项目跟进对照（可选）
    project_report_path = generate_project_tracking_report(
        cfg, os.path.join(SCRIPT_DIR, cfg["output_dir"]), today
    )
    if project_report_path:
        print(f"📌 项目跟进报告：{project_report_path}\n")


if __name__ == "__main__":
    main()

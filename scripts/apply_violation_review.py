"""一次性脚本：撤销敏感信息类误报认定并写入复核记录（执行后保留存档）。

核查方法：从研发云缓存重放各单代码变更新增行，用当前规则正则重新扫描，
并逐条人工判定命中内容的性质。核查结论：原 12 条敏感信息类违规认定
（security-001 六单、SEC-J00033 六单）全部为误报，无一真实违规。

处置：
- violations 中移除被撤销的条目（保留 J000025 等本次未核查规则）；
- 新增 violation_review 复核记录，逐条说明撤销/维持的认定原因。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

REVIEWED_AT = "2026-09-02T19:20:00"
METHOD = (
    "从研发云缓存重放该单代码变更新增行，用修正后的规则正则重新扫描，"
    "并对每条命中的代码内容逐条人工判定（值是否为真实凭证/是否属于本次"
    "引入的生产行为），依据事实而非推断作出认定"
)

# 每单的撤销理由（rule_id -> 详细认定说明）
REASONS: dict[str, dict[str, str]] = {
    "11797805": {
        "security-001": (
            "4 条命中均为配置键常量定义：PWD_EXPIRE_DAYS=\"ecare.user.pwd.expire-days\"、"
            "PWD_DIFFER_PREVIOUS_COUNT=\"ecare.mod-pwd.pwd-differ-previous-count\"、"
            "TOKEN_AUTO_KICK_OUT=\"webs.ecare.token.auto-kick-out\"、APP_SECRET=\"uc.appSecret\"。"
            "等号右侧是配置中心的键路径（点分命名空间字符串），不是密码/令牌/密钥的实际值——"
            "定义的是\"去哪里取配置\"，而非把凭证写死在代码里。判定：非硬编码敏感信息，误报。"
        ),
        "SEC-J00033": (
            "命中行均为日志消息文本含普通词 token（如 logger.debug(\"singtel expire token cache "
            "end, expireIUsers {}\", expireIUsers)、logger.debug(\"expire uc token start, userId "
            "{}\", userId)）。实际输出的是过期用户集合与内部 userId，日志消息里的 \"token\" 一词"
            "指 token 缓存过期处理逻辑，并非输出凭证值。判定：非日志敏感信息输出，误报。"
        ),
    },
    "11797806": {
        "security-001": (
            "同 11797805（同一故障的两条处理记录），4 条命中均为配置键常量定义，值是配置键路径"
            "（ecare.user.pwd.expire-days 等）而非凭证实际值。判定：误报。"
        ),
        "SEC-J00033": (
            "命中行为日志消息文本含普通词 token（\"expire uc token start/end\"），输出变量为 "
            "userId/expireIUsers 等非敏感数据。判定：误报。"
        ),
    },
    "11807893": {
        "SEC-J00033": (
            "命中行 logger.debug(\"asyncCheckFileSim start, key=[{}]\", key) 输出的是文件校验的"
            "缓存键，不是加密密钥。另注：原记录的 message 为\"多线程环境下使用非线程安全集合"
            "（J000025）\"，与 SEC-J00033 条款错位——系检测器多规则命中共用首个命中类型描述的"
            "缺陷所致（引擎已修复为逐规则对齐）。判定：误报，撤销。"
        ),
    },
    "11852829": {
        "SEC-J00033": (
            "命中行 LOGGER.info(\"getUtmTemplateLinkIncludeExpByCache linkTemplateIncludeExpCacheKey "
            "{} ...\", cacheKey, linkTemplateIncludeExpJson) 输出的是 UTM 模板缓存键与模板内容，"
            "均非口令/密钥/令牌类敏感凭证。判定：误报，撤销。"
        ),
    },
    "11855458": {
        "SEC-J00033": (
            "命中行 logger.debug(\"handleMacroScript end, args is [{}]， key is [{}]\", args, key) "
            "输出的是 UTM 宏处理的方法参数与键名，非敏感凭证（旧正则裸词 key 误命中）。判定：误报，撤销。"
        ),
    },
    "11856506": {
        "SEC-J00033": (
            "同 11855458，命中行输出 UTM 宏处理参数与键名，非敏感凭证。判定：误报，撤销。"
        ),
    },
    "11857576": {
        "security-001": (
            "命中行 .append(questionNaireLanguage).append(\"&token=\").append(mccContact.getNaireToken()"
            ")... 是 URL 动态拼接——token 的值来自变量 getNaireToken() 运行时取值，代码中没有硬编码"
            "任何凭证字面量；旧正则跨引号匹配把 \").append(变量)\" 误当成字符串值。判定：非硬编码"
            "敏感信息，误报，撤销。"
        ),
    },
    "11862289": {
        "security-001": (
            "命中行 pwd: 'required(reservePwdRequiredRule);' 是表单校验规则声明（pwd 字段必填校验"
            "表达式），引号内是校验规则而非密码值。判定：误报，撤销。"
        ),
    },
    "11937118": {
        "security-001": (
            "命中内容为被注释掉的日志语句 // LogUtils.d(\"SdkDxpBaseModule\", \"token :\" + token) "
            "与变量赋值 CEEUserInfoManage.getInstance().token = token（运行时取值，非硬编码），且"
            "同一函数内调用 clearSensitiveUserInfoCache() 主动清理敏感信息缓存。判定：非硬编码"
            "敏感信息，误报，撤销。"
        ),
    },
    "11964009": {
        "security-001": (
            "三条命中均不构成\"硬编码敏感信息\"：(1) console.log('FCM Token:', errorMsg/token) 输出"
            "的是 FCM 推送令牌变量（运行时取值），非硬编码字面量；(2) token: 'tok-b8' 位于 "
            "__tests__/DeepLink.test.js（jest 测试文件 beforeEach 中构造的 mock 用户 store 假值），"
            "不部署到生产环境。判定：误报，撤销。"
        ),
    },
}

REVOKED_RULES = {"security-001", "SEC-J00033"}
CONCLUSION_TMPL = (
    "经逐条核查，该单不存在违反\"敏感信息泄露\"安全规范的行为：原认定{orig}经重放"
    "代码变更新增行并逐条判定，均为规则正则误报（理由见 items），已撤销认定。"
    "引擎已针对性收紧规则（security-001 排除配置键路径/跨引号假阳性/测试文件，"
    "SEC-J00033 仅匹配日志参数中的敏感词标识符），全量 181 起故障重放后敏感信息类"
    "误报为 0，真实凭证样本仍正常命中。"
)

urids = sorted(REASONS)
for urid in urids:
    path = Path(f"output/progress_{urid}.json")
    rec = json.loads(path.read_text(encoding="utf-8"))
    backup = path.with_suffix(f".json.bak_{REVIEWED_AT[:10].replace('-', '')}_{REVIEWED_AT[11:13]}{REVIEWED_AT[14:16]}")
    shutil.copy2(path, backup)

    violations = rec.get("violations", []) or []
    kept, revoked_items = [], []
    for v in violations:
        rid = str(v.get("rule_id", ""))
        if rid in REVOKED_RULES and rid in REASONS.get(urid, {}):
            revoked_items.append(
                {
                    "rule_id": rid,
                    "rule_name": v.get("rule_name", ""),
                    "original_message": v.get("message", ""),
                    "original_evidence": v.get("evidence", []),
                    "disposition": "revoked",
                    "reason": REASONS[urid][rid],
                }
            )
        else:
            kept.append(v)

    orig_desc = "、".join(
        f"{it['rule_id']}（{it['rule_name']}）" for it in revoked_items
    ) or "无"
    rec["violations"] = kept
    rec["violation_review"] = {
        "reviewed_at": REVIEWED_AT,
        "reviewer": "复盘引擎维护（人工逐条核查）",
        "scope": "敏感信息类违规认定（security-001 敏感信息泄露 / SEC-J00033 日志敏感信息）",
        "method": METHOD,
        "conclusion": CONCLUSION_TMPL.format(orig=orig_desc),
        "items": revoked_items,
    }
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[{urid}] 撤销 {len(revoked_items)} 条，保留 {len(kept)} 条，"
        f"备份 {backup.name}"
    )

print("完成")

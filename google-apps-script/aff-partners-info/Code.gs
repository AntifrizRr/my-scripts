/***************
 * НАСТРОЙКИ
 ***************/
const SHEET_NAME = "Approves partner's deals";
const TARGET_ACTIVE_SHEET_NAME = "Monthly Partner's active campaigns";
const SLACKLOG_SHEET_NAME = "SlackLog";
const MONTHLY_ALERTLOG_SHEET_NAME = "MonthlyAlertLog";

function getProp_(key, fallback) {
  const rawValue = PropertiesService.getScriptProperties().getProperty(key);
  if (rawValue === null || rawValue === "") return fallback;
  return rawValue;
}

function parseAffManagerStatusTags_(rawValue) {
  try {
    const parsed = JSON.parse(rawValue || "{}") || {};
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }

    const result = {};
    Object.entries(parsed).forEach(([key, value]) => {
      result[String(key).trim().toLowerCase()] = String(value);
    });
    return result;
  } catch (err) {
    Logger.log(`Failed to parse AFF_MANAGER_STATUS_TAGS_JSON: ${err}`);
    return {};
  }
}

const PF_SPREADSHEET_ID = getProp_("PF_SPREADSHEET_ID", "REPLACE_WITH_SPREADSHEET_ID");
const PF_SHEET_NAME = getProp_("PF_SHEET_NAME", "SEO Обзорники");
const PF_PLATFORM_NAME = getProp_("PF_PLATFORM_NAME", "partner-platform");

// ===== unique_key для Monthly -> SEO Обзорники =====
const MONTHLY_UNIQUE_KEY_HEADER_NAMES = ["unique_key", "Unique key", "Unique Key"];
const PF_UNIQUE_KEY_HEADER_NAMES = ["unique_key", "Unique key", "Unique Key"];

// ===== Partner Base -> План/Факт: Affiliate_manager =====
const AFF_PARTNER_BASE_SHEET_NAME = "Partner Base";
const PF_AFFILKA_DIRECTORY_SHEET_NAME = "Справочник Affilka";
const PF_AFFILIATE_CHANGELOG_SHEET_NAME = "affiliate_change";

const AFF_BASE_COL_PARTNER_ID_NAMES = ["Partner ID"];
const AFF_BASE_COL_AFF_MANAGER_NAMES = ["Aff manager"];

const PF_AFFILKA_COL_AFFILIATE_ID_NAMES = ["Affiliate ID"];
const PF_AFFILKA_COL_AFFILIATE_MANAGER_NAMES = ["Affiliate_manager"];
const PF_AFFILKA_COL_CAMPAIGN_ID_NAMES = ["Campaign ID"];

const AFFILIATE_CHANGELOG_HEADERS = ["Date", "Campaign ID", "New_Aff_manager", "Old_Aff_manager"];

// ===== Поиск партнёров / статистика =====
const SEARCH_PARTNERS_SHEET_NAME = "Поиск партнёров";
const SEARCH_PARTNERS_STATS_SHEET_NAME = "Поиск партнеров стат.";
const SEARCH_STATE_LOG_PREFIX = "SEARCHSTATE";
const SEARCH_COL_RESET_MARKER_NAMES = ["Последний сброс чекбоксов", "Reset marker"];

// Источник: Поиск партнёров
const SEARCH_COL_PARTNER_NAME_NAMES = ["Partner name", "Partner Name", "Партнер", "Партнёр"];
const SEARCH_COL_SITE_NAMES = ["Сайт SEO", "Site", "Website", "Domain", "Домен"];
const SEARCH_COL_STATUS_NAMES = ["Status", "Статус"];
const SEARCH_COL_PING_NAMES = ["Написали/пинганули", "Написали / пинганули", "Написали", "Пинганули"];
const SEARCH_COL_AFF_MANAGER_NAMES = ["Aff manager", "Aff Manager", "Афф менеджер", "Affmanager"];
const SEARCH_COL_CONTACT_NAMES = ["Contact", "Контакт", "Contacts"];

// Статистика: Поиск партнеров стат.
const SEARCH_STATS_COL_PERIOD_NAMES = ["Период", "Period"];
const SEARCH_STATS_COL_NEW_SITES_NAMES = ["Новых сайтов добавлено", "New sites added"];
const SEARCH_STATS_COL_PINGED_NAMES = ["Написали/пинганули", "Отписано / пинганули", "Written / pinged"];
const SEARCH_STATS_COL_AFF_MANAGER_NAMES = ["Aff manager", "Aff Manager", "Афф менеджер"];

// Названия колонок
const COL_STATUS_NAMES = ["Approval status", "Approval status from Head of Aff"];
const COL_PARTNER_ID_NAMES = ["Partner ID"];
const COL_CAMPAIGN_ID_NAMES = ["Campaign ID"];
const COL_DEAL_TYPE_NAMES = ["Deal type"];
const COL_ANALYST_INFO_NAMES = ["Info from analyst"];
const COL_CHECKING_ANALYTICS_NAMES = ["Checking analytics"];

// Monthly alert columns
const COL_MONTHLY_TYPE_NAMES = ["FF/Setup fee"];
const COL_MONTHLY_AMOUNT_NAMES = ["Сумма FF/setup fee"];
const COL_MONTHLY_PAYMENT_TERM_NAMES = ["Срок оплаты FF/Setup fee"];

const MONTHLY_ALERT_WEBHOOK_URL = getProp_("MONTHLY_ALERT_WEBHOOK_URL", "https://example.invalid/webhook");
const MONTHLY_TRIGGER_TYPES = new Set(["ff", "setup fee"]);

// Значения статусов
const ON_APPROVAL_VALUE = "On approval";
const APPROVED_VALUE = "Approved";

// Поля для переноса в Monthly Partner's active campaigns
const ACTIVE_CAMPAIGN_TRANSFER_MAP = [
  { source: "Period", target: "Period", fallbackSource: "Deal period" },
  { source: "Aff manager", target: "Aff manager" },
  { source: "Partner Name", target: "Partner Name" },
  { source: "Partner ID", target: "Partner ID" },
  { source: "Campaign ID", target: "Campaign ID" },
  { source: "GEO", target: "GEO" },
  { source: "Traffic source campaign", target: "Traffic source campaign" }
];

// Deal type значения, при которых пингуем аналитика при постановке On approval
const DEAL_TYPES_PING_ANALYST = new Set([
  "Текущая сделка",
  "Текущая сделка с UP условий",
]);

// Теги (через Slack USER ID или безопасные placeholder-значения)
const TAG_ON_APPROVAL = getProp_("SLACK_ON_APPROVAL_MENTION", "<@example>");
const TAG_OTHER_STATUSES_DEFAULT = getProp_("SLACK_DEFAULT_STATUS_MENTION", "<@ops>");
const TAG_ANALYST = getProp_("SLACK_ANALYST_MENTION", "<@analyst>");

// Маппинг Aff manager -> кто получает пинг по смене статуса
const AFF_MANAGER_STATUS_TAGS = parseAffManagerStatusTags_(getProp_("AFF_MANAGER_STATUS_TAGS_JSON", '{"ops":"<@ops>"}'));

// Реакции по статусам
const STATUS_REACTIONS = {
  "Approved": "white_check_mark",
  "Declined": "x",
  "Pause of approval": "warning",
};

// Какие реакции чистим при смене статуса
const MANAGED_REACTIONS = new Set(Object.values(STATUS_REACTIONS));

// Торможение, чтобы не ловить лимиты Slack/Apps Script
const THROTTLE_EVERY_N_ROWS = 15;
const THROTTLE_SLEEP_MS = 600;

// Антидубль только для нового On approval
const ON_APPROVAL_DEDUPE_WINDOW_MS = 120000; // 2 минуты

// Колонки для синка в п/ф
const PF_HEADERS = {
  sourceId: "Source ID",
  platform: "Platform",
  periodStart: "period start",
  periodFinish: "period finish",
  feeEuro: "Fee евро",
  type: "type",
  status: "status",
  geo: "GEO",
  position: "position",
  webmasterId: "id вебмастера"
};

// Какие колонки на Monthly отслеживаем для синка в п/ф
const MONTHLY_TO_PF_SOURCE_HEADERS = {
  campaignId: ["Campaign ID"],
  startPeriod: ["Start period with FF/Setup fee"],
  endPeriod: ["End period with FF/Setup fee"],
  feeAmount: ["Сумма FF/setup fee"],
  feeType: ["FF/Setup fee"],
  dealStatus: ["Deal status"],
  geo: ["GEO"],
  position: ["Позиция на сайте нашего бренда"],
  partnerId: ["Partner ID"]
};

// Маппинг статусов Monthly -> п/ф
const PF_STATUS_MAP = {
  "запущен (ждем лиды)": "размещены",
  "запущен (лиды идут)": "размещены",
  "в очереди на запуск": "не размещены",
  "отказ запуска": "не размещены"
};

/***************
 * ТРИГГЕР
 ***************/
function onEdit(e) {
  if (!e || !e.range) return;

  try {
    const sheet = e.range.getSheet();
    if (!sheet) return;

    const sheetName = sheet.getName();

    // ===== ЛОГИКА ДЛЯ Approves partner's deals =====
    if (sheetName === SHEET_NAME) {
      const lastCol = sheet.getLastColumn();
      const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
      const headerMap = buildHeaderMap_(headers);

      const colStatus = findHeaderIndexByVariants_(headerMap, COL_STATUS_NAMES, true);
      const colCheckingAnalytics = findHeaderIndexByVariants_(headerMap, COL_CHECKING_ANALYTICS_NAMES, false);

      const editedCol = e.range.getColumn();
      const editedStatus = editedCol === colStatus;
      const editedAnalyticsCheck = !!colCheckingAnalytics && editedCol === colCheckingAnalytics;
      if (!editedStatus && !editedAnalyticsCheck) return;

      const startRow = e.range.getRow();
      const numRows = e.range.getNumRows();
      const rowsData = sheet.getRange(startRow, 1, numRows, lastCol).getValues();

      const ctx = buildRuntimeContext_(sheet, headers, headerMap);

      let processed = 0;
      for (let i = 0; i < numRows; i++) {
        const rowNumber = startRow + i;
        if (rowNumber === 1) continue;

        try {
          processRowEvent_(ctx, rowNumber, rowsData[i], editedCol, colStatus, colCheckingAnalytics);
        } catch (err) {
          Logger.log(`Row ${rowNumber} error: ${err}\n${err.stack || ""}`);
        }

        processed++;
        if (processed % THROTTLE_EVERY_N_ROWS === 0) {
          Utilities.sleep(THROTTLE_SLEEP_MS);
        }
      }

      flushSlackLogCache_(ctx.logCache);
      flushActiveCache_(ctx.activeCache);
      return;
    }

    // ===== ЛОГИКА ДЛЯ Monthly Partner's active campaigns =====
    if (sheetName === TARGET_ACTIVE_SHEET_NAME) {
      processMonthlySheetAlert_(e, sheet);
      syncMonthlyRowToPlanFact_(e, sheet);
      return;
    }

    // ===== ЛОГИКА ДЛЯ Partner Base =====
    if (sheetName === AFF_PARTNER_BASE_SHEET_NAME) {
      processPartnerBaseAffiliateManagerSync_(e, sheet);
      return;
    }

    // ===== ЛОГИКА ДЛЯ Поиск партнёров =====
    if (sheetName === SEARCH_PARTNERS_SHEET_NAME) {
      processSearchPartnersStats_(e, sheet);
      return;
    }
  } catch (err) {
    Logger.log(`onEdit fatal: ${err}\n${err.stack || ""}`);
    throw err;
  }
}

/***************
 * КОНТЕКСТ / КЭШ
 ***************/
function buildRuntimeContext_(sourceSheet, headers, headerMap) {
  const ss = SpreadsheetApp.getActive();
  const logSheet = ensureSlackLog_();

  return {
    ss,
    sourceSheet,
    headers,
    headerMap,
    channelId: getProp_("SLACK_CHANNEL"),
    logCache: loadSlackLogCache_(logSheet),
    activeCache: null,
  };
}

function ensureActiveCache_(ctx) {
  if (ctx.activeCache) return ctx.activeCache;

  const targetSheet = ctx.ss.getSheetByName(TARGET_ACTIVE_SHEET_NAME);
  if (!targetSheet) {
    throw new Error(`Не найден лист: ${TARGET_ACTIVE_SHEET_NAME}`);
  }

  const targetLastCol = targetSheet.getLastColumn();
  const targetHeaders = targetSheet.getRange(1, 1, 1, targetLastCol).getValues()[0];
  const targetHeaderMap = buildHeaderMap_(targetHeaders);

  const targetColIndexes = {};
  for (const item of ACTIVE_CAMPAIGN_TRANSFER_MAP) {
    targetColIndexes[item.target] = findHeaderIndexByVariants_(targetHeaderMap, [item.target], true);
  }

  const periodIdx = findHeaderIndexByVariants_(targetHeaderMap, ["Period"], true) - 1;
  const partnerIdx = findHeaderIndexByVariants_(targetHeaderMap, ["Partner ID"], true) - 1;
  const campaignIdx = findHeaderIndexByVariants_(targetHeaderMap, ["Campaign ID"], true) - 1;
  const geoIdx = findHeaderIndexByVariants_(targetHeaderMap, ["GEO"], true) - 1;
  const trafficIdx = findHeaderIndexByVariants_(targetHeaderMap, ["Traffic source campaign"], true) - 1;

  const lastRow = Math.max(targetSheet.getLastRow(), 2);
  const dataAll = lastRow >= 2
    ? targetSheet.getRange(2, 1, lastRow - 1, Math.max(targetLastCol, 6)).getValues()
    : [];

  const existingSignatures = new Set();
  const occupancy = [];

  for (let i = 0; i < dataAll.length; i++) {
    const row = dataAll[i];

    const existingPartnerId = row[partnerIdx];
    const existingCampaignId = row[campaignIdx];
    const existingPeriod = row[periodIdx];
    const existingGeo = row[geoIdx];
    const existingTraffic = row[trafficIdx];

    if (
      String(existingPartnerId || "").trim() ||
      String(existingCampaignId || "").trim() ||
      String(existingPeriod || "").trim() ||
      String(existingGeo || "").trim() ||
      String(existingTraffic || "").trim()
    ) {
      existingSignatures.add(
        makeActiveCampaignSignature_(
          existingPartnerId,
          existingCampaignId,
          existingPeriod,
          existingGeo,
          existingTraffic
        )
      );
    }

    const colA = String(row[0] || "").trim();
    const colC = String(row[2] || "").trim();
    const colD = String(row[3] || "").trim();
    const colE = String(row[4] || "").trim();
    const colF = String(row[5] || "").trim();
    occupancy.push(!!(colA || colC || colD || colE || colF));
  }

  ctx.activeCache = {
    sheet: targetSheet,
    targetLastCol,
    targetHeaders,
    targetHeaderMap,
    targetColIndexes,
    existingSignatures,
    occupancy,
    pendingRows: new Map()
  };

  return ctx.activeCache;
}

/***************
 * ПОИСК КОЛОНОК
 ***************/
function normalizeHeader_(value) {
  return String(value || "")
    .trim()
    .replace(/[\t\r\n]+/g, " ")
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function buildHeaderMap_(headers) {
  const map = {};
  headers.forEach((h, idx) => {
    map[normalizeHeader_(h)] = idx + 1;
  });
  return map;
}

function findHeaderIndexByVariants_(headerMap, variants, required) {
  for (const variant of variants) {
    const idx = headerMap[normalizeHeader_(variant)];
    if (idx) return idx;
  }
  if (required) {
    throw new Error(`Не найдена колонка: ${variants.join(" / ")}`);
  }
  return null;
}

function getCellByHeaderVariants_(rowValues, headerMap, variants) {
  const idx = findHeaderIndexByVariants_(headerMap, variants, false);
  return idx ? rowValues[idx - 1] : "";
}

function getStatusTagByAffManager_(affManagerRaw) {
  const key = normalizeHeader_(affManagerRaw);
  return AFF_MANAGER_STATUS_TAGS[key] || TAG_OTHER_STATUSES_DEFAULT;
}

/***************
 * КЛЮЧИ / МИГРАЦИЯ
 ***************/
function makeKeys_(partnerId, campaignId, row) {
  const rowKey = `${partnerId}|ROW${row}`;
  const normalKey = campaignId ? `${partnerId}|${campaignId}` : "";
  return { rowKey, normalKey };
}

function getEntryWithMigrationCached_(logCache, partnerId, campaignId, row) {
  const { rowKey, normalKey } = makeKeys_(partnerId, campaignId, row);

  if (normalKey) {
    const byNormal = getLogEntryCached_(logCache, normalKey);
    if (byNormal) return { key: normalKey, entry: byNormal, migrated: false };

    const byRow = getLogEntryCached_(logCache, rowKey);
    if (byRow) {
      upsertLogEntryCached_(logCache, normalKey, {
        thread_ts: byRow.thread_ts,
        last_status: byRow.last_status,
        onapproval_count: byRow.onapproval_count || 0,
        analyst_info_hash: byRow.analyst_info_hash || "",
        last_onapproval_sig: byRow.last_onapproval_sig || "",
        last_onapproval_at: byRow.last_onapproval_at || ""
      });
      deleteLogEntryCached_(logCache, rowKey);
      return { key: normalKey, entry: getLogEntryCached_(logCache, normalKey), migrated: true };
    }

    return { key: normalKey, entry: null, migrated: false };
  }

  return { key: rowKey, entry: getLogEntryCached_(logCache, rowKey), migrated: false };
}

/***************
 * ОБРАБОТКА СТРОКИ Approves partner's deals
 ***************/
function processRowEvent_(ctx, row, rowValues, editedCol, colStatus, colCheckingAnalytics) {
  const get = (variants) => getCellByHeaderVariants_(rowValues, ctx.headerMap, variants);

  const status = String(get(COL_STATUS_NAMES) || "").trim();
  const partnerId = String(get(COL_PARTNER_ID_NAMES) || "").trim();
  const campaignId = String(get(COL_CAMPAIGN_ID_NAMES) || "").trim();
  const dealType = String(get(COL_DEAL_TYPE_NAMES) || "").trim();
  const analystInfo = String(get(COL_ANALYST_INFO_NAMES) || "").trim();
  const checkingAnalyticsValue = get(COL_CHECKING_ANALYTICS_NAMES);
  const affManager = String(get(["Aff manager"]) || "").trim();
  const statusTag = getStatusTagByAffManager_(affManager);

  if (!partnerId) return;

  const link = buildRowLink_(ctx.sourceSheet, row, ctx.headers.length);
  const found = getEntryWithMigrationCached_(ctx.logCache, partnerId, campaignId, row);
  const key = found.key;
  const entry = found.entry;

  if (editedCol === colStatus) {
    if (status === ON_APPROVAL_VALUE) {
      const signature = `${key}|${row}|${ON_APPROVAL_VALUE}`;
      const nowMs = Date.now();
      if (
        entry &&
        String(entry.last_status || "").trim() === ON_APPROVAL_VALUE &&
        String(entry.last_onapproval_sig || "") === signature &&
        Number(entry.last_onapproval_at || 0) > 0 &&
        nowMs - Number(entry.last_onapproval_at) <= ON_APPROVAL_DEDUPE_WINDOW_MS
      ) {
        Logger.log(`On approval duplicate suppressed for row ${row}`);
        return;
      }

      const isRepeat = Boolean(entry);
      const textCore = buildOnApprovalMessage_(ctx.headers, rowValues, row, isRepeat);

      const pingAnalyst = DEAL_TYPES_PING_ANALYST.has(dealType);
      const mentions = pingAnalyst ? `${TAG_ON_APPROVAL} ${TAG_ANALYST}` : `${TAG_ON_APPROVAL}`;
      const text = `${mentions}\n${textCore}\n\n🔗 ${link}`;

      const res = slackPostMessage_({
        channel: ctx.channelId,
        text
      });

      upsertLogEntryCached_(ctx.logCache, key, {
        thread_ts: res.ts,
        last_status: status,
        onapproval_count: (entry?.onapproval_count || 0) + 1,
        analyst_info_hash: "",
        last_onapproval_sig: signature,
        last_onapproval_at: String(nowMs)
      });

      return;
    }

    if (!status) return;

    if (!entry || !entry.thread_ts) {
      const warn =
        `⚠️ *Тред не найден, проверь SlackLog* — статус: *${status}* (строка ${row})\n` +
        `Partner ID: *${partnerId}*${campaignId ? ` | Campaign ID: *${campaignId}*` : ""}\n` +
        `🔗 ${link}`;

      slackPostMessage_({
        channel: ctx.channelId,
        text: `${statusTag}\n${warn}`
      });

      if (status === APPROVED_VALUE) {
        appendApprovedDealToActiveCampaignsCached_(ctx, rowValues);
      }
      return;
    }

    const threadTs = normalizeThreadTs_(entry.thread_ts);
    if (!threadTs) {
      const warn =
        `⚠️ *Тред не найден, проверь SlackLog (битый thread_ts)* — статус: *${status}* (строка ${row})\n` +
        `Partner ID: *${partnerId}*${campaignId ? ` | Campaign ID: *${campaignId}*` : ""}\n` +
        `🔗 ${link}`;

      slackPostMessage_({
        channel: ctx.channelId,
        text: `${statusTag}\n${warn}`
      });

      if (status === APPROVED_VALUE) {
        appendApprovedDealToActiveCampaignsCached_(ctx, rowValues);
      }
      return;
    }

    if ((entry.last_status || "") === status) return;

    const reply =
      `Статус изменён: *${entry.last_status || ON_APPROVAL_VALUE}* → *${status}* (строка ${row})\n` +
      `🔗 ${link}`;

    slackPostMessage_({
      channel: ctx.channelId,
      text: `${statusTag}\n${reply}`,
      thread_ts: threadTs
    });

    try {
      removeManagedReactions_(ctx.channelId, threadTs);
      const reactionName = STATUS_REACTIONS[status];
      if (reactionName) slackAddReaction_(ctx.channelId, threadTs, reactionName);
    } catch (err) {
      Logger.log(`Reactions error row ${row}: ${err}\n${err.stack || ""}`);
    }

    if (status === APPROVED_VALUE) {
      appendApprovedDealToActiveCampaignsCached_(ctx, rowValues);
    }

    upsertLogEntryCached_(ctx.logCache, key, {
      thread_ts: threadTs,
      last_status: status,
      onapproval_count: entry.onapproval_count || 0,
      analyst_info_hash: entry.analyst_info_hash || "",
      last_onapproval_sig: entry.last_onapproval_sig || "",
      last_onapproval_at: entry.last_onapproval_at || ""
    });

    return;
  }

  if (colCheckingAnalytics && editedCol === colCheckingAnalytics) {
    if (status !== ON_APPROVAL_VALUE) return;
    if (!DEAL_TYPES_PING_ANALYST.has(dealType)) return;

    const isChecked = checkingAnalyticsValue === true || String(checkingAnalyticsValue).toUpperCase() === "TRUE";
    if (!isChecked) return;
    if (!analystInfo) return;

    if (!entry || !entry.thread_ts) {
      const warn =
        `⚠️ *Аналитика отмечена, но тред не найден — проверь SlackLog* (строка ${row})\n` +
        `Partner ID: *${partnerId}*${campaignId ? ` | Campaign ID: *${campaignId}*` : ""}\n` +
        `🔗 ${link}`;

      slackPostMessage_({
        channel: ctx.channelId,
        text: `${TAG_ON_APPROVAL}\n${warn}`
      });
      return;
    }

    const threadTs = normalizeThreadTs_(entry.thread_ts);
    if (!threadTs) return;

    const newHash = hashText_(analystInfo);
    const oldHash = String(entry.analyst_info_hash || "").trim();
    if (oldHash && oldHash === newHash) return;

    const msg =
      `🔁 *Аналитика добавлена* (строка ${row})\n` +
      `*Deal type:* ${dealType}\n` +
      `*Info from analyst:*\n>${analystInfo.replace(/\n/g, "\n>")}\n\n` +
      `${TAG_ON_APPROVAL}\n` +
      `🔗 ${link}`;

    slackPostMessage_({
      channel: ctx.channelId,
      text: msg,
      thread_ts: threadTs
    });

    try {
      slackAddReaction_(ctx.channelId, threadTs, "eyes");
    } catch (err) {
      Logger.log(`eyes reaction error row ${row}: ${err}`);
    }

    upsertLogEntryCached_(ctx.logCache, key, {
      thread_ts: threadTs,
      last_status: entry.last_status || ON_APPROVAL_VALUE,
      onapproval_count: entry.onapproval_count || 0,
      analyst_info_hash: newHash,
      last_onapproval_sig: entry.last_onapproval_sig || "",
      last_onapproval_at: entry.last_onapproval_at || ""
    });
  }
}

/***************
 * ПЕРЕНОС APPROVED СДЕЛКИ
 ***************/
function appendApprovedDealToActiveCampaignsCached_(ctx, rowValues) {
  const cache = ensureActiveCache_(ctx);

  const getSourceValue = (name, fallbackName) => {
    let idx = ctx.headerMap[normalizeHeader_(name)];
    if (!idx && fallbackName) {
      idx = ctx.headerMap[normalizeHeader_(fallbackName)];
    }
    return idx ? rowValues[idx - 1] : "";
  };

  const partnerId = String(getSourceValue("Partner ID") || "").trim();
  const campaignId = String(getSourceValue("Campaign ID") || "").trim();
  const period = String(getSourceValue("Period", "Deal period") || "").trim();
  const geo = String(getSourceValue("GEO") || "").trim();
  const traffic = String(getSourceValue("Traffic source campaign") || "").trim();

  const signature = makeActiveCampaignSignature_(partnerId, campaignId, period, geo, traffic);

  if (cache.existingSignatures.has(signature)) return;

  const newRow = findFirstEmptyActiveCampaignRowCached_(cache);
  const fullRow = new Array(cache.targetLastCol).fill("");

  for (const item of ACTIVE_CAMPAIGN_TRANSFER_MAP) {
    const targetCol = cache.targetColIndexes[item.target];
    fullRow[targetCol - 1] = getSourceValue(item.source, item.fallbackSource);
  }

  cache.pendingRows.set(newRow, fullRow);
  cache.existingSignatures.add(signature);

  const occIdx = newRow - 2;
  while (cache.occupancy.length <= occIdx) cache.occupancy.push(false);
  cache.occupancy[occIdx] = true;
}

function normalizeCompareValue_(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function normalizeSimpleString_(value) {
  return String(value == null ? "" : value).trim();
}

function normalizeIdValue_(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") {
    return String(value).trim();
  }
  return String(value).replace(/\s+/g, "").trim();
}

function splitPartnerIds_(value) {
  const raw = String(value == null ? "" : value).trim();
  if (!raw) return [];

  return raw
    .split(/[\n,;]+/)
    .map(v => normalizeIdValue_(v))
    .filter(Boolean);
}

function makeActiveCampaignSignature_(partnerId, campaignId, period, geo, traffic) {
  return [
    normalizeCompareValue_(partnerId),
    normalizeCompareValue_(campaignId),
    normalizeCompareValue_(period),
    normalizeCompareValue_(geo),
    normalizeCompareValue_(traffic)
  ].join("|");
}

function findFirstEmptyActiveCampaignRowCached_(cache) {
  for (let i = 0; i < cache.occupancy.length; i++) {
    if (!cache.occupancy[i]) return i + 2;
  }
  return cache.occupancy.length + 2;
}

function flushActiveCache_(cache) {
  if (!cache || cache.pendingRows.size === 0) return;

  const rows = Array.from(cache.pendingRows.keys()).sort((a, b) => a - b);
  for (const row of rows) {
    cache.sheet.getRange(row, 1, 1, cache.targetLastCol).setValues([cache.pendingRows.get(row)]);
  }
  cache.pendingRows.clear();
}

/***************
 * PARTNER BASE -> ПЛАН/ФАКТ: AFFILIATE_MANAGER
 ***************/
function processPartnerBaseAffiliateManagerSync_(e, sourceSheet) {
  const lastCol = sourceSheet.getLastColumn();
  if (lastCol < 1) return;

  const headers = sourceSheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);

  const colPartnerId = findHeaderIndexByVariants_(headerMap, AFF_BASE_COL_PARTNER_ID_NAMES, true);
  const colAffManager = findHeaderIndexByVariants_(headerMap, AFF_BASE_COL_AFF_MANAGER_NAMES, true);

  const editStartCol = e.range.getColumn();
  const editEndCol = editStartCol + e.range.getNumColumns() - 1;

  const touchesPartnerId = colPartnerId >= editStartCol && colPartnerId <= editEndCol;
  const touchesAffManager = colAffManager >= editStartCol && colAffManager <= editEndCol;

  if (!touchesPartnerId && !touchesAffManager) return;
  if (e.range.getRow() === 1) return;

  syncAffiliateManagersFromPartnerBaseToPlanFact_();
}

function syncAffiliateManagersFromPartnerBaseToPlanFact_() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) {
    Logger.log("Skipping affiliate manager sync because a script lock could not be acquired.");
    return;
  }

  try {
    const sourceSs = SpreadsheetApp.getActive();
    const sourceSheet = sourceSs.getSheetByName(AFF_PARTNER_BASE_SHEET_NAME);
    if (!sourceSheet) {
      throw new Error(`Не найден лист: ${AFF_PARTNER_BASE_SHEET_NAME}`);
    }

    const pfSs = SpreadsheetApp.openById(PF_SPREADSHEET_ID);
    const pfSheet = pfSs.getSheetByName(PF_AFFILKA_DIRECTORY_SHEET_NAME);
    if (!pfSheet) {
      throw new Error(`Не найден лист п/ф: ${PF_AFFILKA_DIRECTORY_SHEET_NAME}`);
    }

    const changeLogSheet = ensureAffiliateChangeLogSheet_(pfSs);

    const sourceLastCol = sourceSheet.getLastColumn();
    const sourceLastRow = sourceSheet.getLastRow();
    if (sourceLastCol < 1 || sourceLastRow < 2) return;

    const sourceHeaders = sourceSheet.getRange(1, 1, 1, sourceLastCol).getValues()[0];
    const sourceHeaderMap = buildHeaderMap_(sourceHeaders);

    const sourcePartnerIdCol = findHeaderIndexByVariants_(sourceHeaderMap, AFF_BASE_COL_PARTNER_ID_NAMES, true);
    const sourceAffManagerCol = findHeaderIndexByVariants_(sourceHeaderMap, AFF_BASE_COL_AFF_MANAGER_NAMES, true);

    const sourceData = sourceSheet.getRange(2, 1, sourceLastRow - 1, sourceLastCol).getValues();

    const partnerIdToAffManager = {};
    for (let i = 0; i < sourceData.length; i++) {
      const row = sourceData[i];
      const ids = splitPartnerIds_(row[sourcePartnerIdCol - 1]);
      const manager = normalizeSimpleString_(row[sourceAffManagerCol - 1]);

      if (!ids.length) continue;

      for (const id of ids) {
        partnerIdToAffManager[id] = manager;
      }
    }

    const pfLastCol = pfSheet.getLastColumn();
    const pfLastRow = pfSheet.getLastRow();
    if (pfLastCol < 1 || pfLastRow < 2) return;

    const pfHeaders = pfSheet.getRange(1, 1, 1, pfLastCol).getValues()[0];
    const pfHeaderMap = buildHeaderMap_(pfHeaders);

    const pfAffiliateIdCol = findHeaderIndexByVariants_(pfHeaderMap, PF_AFFILKA_COL_AFFILIATE_ID_NAMES, true);
    const pfAffiliateManagerCol = findHeaderIndexByVariants_(pfHeaderMap, PF_AFFILKA_COL_AFFILIATE_MANAGER_NAMES, true);
    const pfCampaignIdCol = findHeaderIndexByVariants_(pfHeaderMap, PF_AFFILKA_COL_CAMPAIGN_ID_NAMES, true);

    const pfData = pfSheet.getRange(2, 1, pfLastRow - 1, pfLastCol).getValues();

    const managerWriteRows = [];
    const logRows = [];
    const now = new Date();
    const todayStr = Utilities.formatDate(now, Session.getScriptTimeZone(), "dd.MM.yyyy");

    for (let i = 0; i < pfData.length; i++) {
      const row = pfData[i];
      const sheetRow = i + 2;

      const affiliateId = normalizeIdValue_(row[pfAffiliateIdCol - 1]);
      if (!affiliateId) continue;

      if (!Object.prototype.hasOwnProperty.call(partnerIdToAffManager, affiliateId)) continue;

      const newManager = normalizeSimpleString_(partnerIdToAffManager[affiliateId]);
      const oldManager = normalizeSimpleString_(row[pfAffiliateManagerCol - 1]);

      if (newManager === oldManager) continue;

      managerWriteRows.push({
        row: sheetRow,
        value: newManager
      });

      logRows.push([
        todayStr,
        row[pfCampaignIdCol - 1] || "",
        newManager,
        oldManager
      ]);
    }

    for (const item of managerWriteRows) {
      pfSheet.getRange(item.row, pfAffiliateManagerCol).setValue(item.value);
    }

    if (logRows.length) {
      const startRow = findNextAffiliateChangeLogRow_(changeLogSheet);
      changeLogSheet.getRange(startRow, 1, logRows.length, AFFILIATE_CHANGELOG_HEADERS.length).setValues(logRows);
    }
  } finally {
    lock.releaseLock();
  }
}

function ensureAffiliateChangeLogSheet_(pfSs) {
  let sh = pfSs.getSheetByName(PF_AFFILIATE_CHANGELOG_SHEET_NAME);

  if (!sh) {
    sh = pfSs.insertSheet(PF_AFFILIATE_CHANGELOG_SHEET_NAME);
  }

  const lastCol = Math.max(sh.getLastColumn(), AFFILIATE_CHANGELOG_HEADERS.length);
  const header = sh.getRange(1, 1, 1, lastCol).getValues()[0];

  let needWriteHeader = false;
  for (let i = 0; i < AFFILIATE_CHANGELOG_HEADERS.length; i++) {
    if (String(header[i] || "").trim() !== AFFILIATE_CHANGELOG_HEADERS[i]) {
      needWriteHeader = true;
      break;
    }
  }

  if (needWriteHeader) {
    sh.getRange(1, 1, 1, AFFILIATE_CHANGELOG_HEADERS.length).setValues([AFFILIATE_CHANGELOG_HEADERS]);
  }

  return sh;
}

function findNextAffiliateChangeLogRow_(sheet) {
  const lastRow = Math.max(sheet.getLastRow(), 1);
  if (lastRow < 2) return 2;

  const values = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
  for (let i = values.length - 1; i >= 0; i--) {
    if (String(values[i][0] || "").trim()) {
      return i + 3;
    }
  }
  return 2;
}

function runFullAffiliateManagerSync() {
  syncAffiliateManagersFromPartnerBaseToPlanFact_();
  Logger.log("Partner Base -> Справочник Affilka: sync completed");
}

/***************
 * MONTHLY ALERT LOG
 ***************/
function ensureMonthlyAlertLog_() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(MONTHLY_ALERTLOG_SHEET_NAME);

  if (!sh) {
    try {
      sh = ss.insertSheet(MONTHLY_ALERTLOG_SHEET_NAME);
      sh.getRange(1, 1, 1, 2).setValues([["row_key", "last_signature"]]);
      sh.hideSheet();
    } catch (err) {
      sh = ss.getSheetByName(MONTHLY_ALERTLOG_SHEET_NAME);
      if (!sh) throw err;
    }
  }

  const header = sh.getRange(1, 1, 1, Math.max(1, sh.getLastColumn())).getValues()[0];
  const requiredHeader = ["row_key", "last_signature"];
  const needRewrite = requiredHeader.some((name, idx) => String(header[idx] || "") !== name);

  if (needRewrite) {
    sh.getRange(1, 1, 1, 2).setValues([requiredHeader]);
  }

  return sh;
}

function loadMonthlyAlertLogCache_(sheet) {
  const lastRow = sheet.getLastRow();
  const rows = lastRow >= 2 ? sheet.getRange(2, 1, lastRow - 1, 2).getValues() : [];

  const byKey = new Map();
  for (let i = 0; i < rows.length; i++) {
    const key = String(rows[i][0] || "").trim();
    if (!key) continue;
    byKey.set(key, {
      row: i + 2,
      row_key: key,
      last_signature: String(rows[i][1] || "").trim()
    });
  }

  return {
    sheet,
    byKey,
    nextRow: Math.max(lastRow + 1, 2),
    pendingRows: new Map(),
    clearedRows: new Set()
  };
}

function getMonthlyAlertEntryCached_(cache, rowKey) {
  return cache.byKey.get(rowKey) || null;
}

function upsertMonthlyAlertEntryCached_(cache, rowKey, lastSignature) {
  const entry = getMonthlyAlertEntryCached_(cache, rowKey);
  const row = entry ? entry.row : cache.nextRow++;

  const newEntry = {
    row,
    row_key: rowKey,
    last_signature: String(lastSignature || "")
  };

  cache.byKey.set(rowKey, newEntry);
  cache.pendingRows.set(row, [newEntry.row_key, newEntry.last_signature]);
  cache.clearedRows.delete(row);
}

function clearMonthlyAlertEntryCached_(cache, rowKey) {
  const entry = getMonthlyAlertEntryCached_(cache, rowKey);
  if (!entry) return;

  cache.byKey.delete(rowKey);
  cache.pendingRows.delete(entry.row);
  cache.clearedRows.add(entry.row);
}

function flushMonthlyAlertLogCache_(cache) {
  if (!cache) return;

  if (cache.clearedRows.size > 0) {
    for (const row of Array.from(cache.clearedRows).sort((a, b) => a - b)) {
      cache.sheet.getRange(row, 1, 1, 2).clearContent();
    }
    cache.clearedRows.clear();
  }

  if (cache.pendingRows.size > 0) {
    const rows = Array.from(cache.pendingRows.keys()).sort((a, b) => a - b);
    for (const row of rows) {
      cache.sheet.getRange(row, 1, 1, 2).setValues([cache.pendingRows.get(row)]);
    }
    cache.pendingRows.clear();
  }
}

function makeMonthlyAlertLogKey_(prefix, rowNumber) {
  return `${prefix}|${TARGET_ACTIVE_SHEET_NAME}|ROW${rowNumber}`;
}

/***************
 * MONTHLY SHEET ALERTS
 ***************/
function processMonthlySheetAlert_(e, sheet) {
  const lastCol = sheet.getLastColumn();
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);

  const colType = findHeaderIndexByVariants_(headerMap, COL_MONTHLY_TYPE_NAMES, true);
  const colAmount = findHeaderIndexByVariants_(headerMap, COL_MONTHLY_AMOUNT_NAMES, true);
  const colTerm = findHeaderIndexByVariants_(headerMap, COL_MONTHLY_PAYMENT_TERM_NAMES, true);

  const editedCol = e.range.getColumn();
  const watchedCols = new Set([colType, colAmount, colTerm]);
  if (!watchedCols.has(editedCol)) return;

  const startRow = e.range.getRow();
  const numRows = e.range.getNumRows();
  if (startRow === 1) return;

  const rowsData = sheet.getRange(startRow, 1, numRows, lastCol).getValues();
  const logCache = loadMonthlyAlertLogCache_(ensureMonthlyAlertLog_());

  for (let i = 0; i < rowsData.length; i++) {
    const rowNumber = startRow + i;
    if (rowNumber === 1) continue;

    const rowValues = rowsData[i];
    const rowKey = makeMonthlyAlertLogKey_("ALERT", rowNumber);

    const check = evaluateMonthlyFeeAlert_(rowValues, headerMap);

    if (!check.shouldSend) {
      clearMonthlyAlertEntryCached_(logCache, rowKey);
      continue;
    }

    const existing = getMonthlyAlertEntryCached_(logCache, rowKey);
    if (existing && String(existing.last_signature || "") === check.signature) {
      continue;
    }

    const text = buildMonthlyFeeAlertMessage_(sheet, rowNumber, rowValues, headerMap);
    postToSlackWebhook_(MONTHLY_ALERT_WEBHOOK_URL, text);
    upsertMonthlyAlertEntryCached_(logCache, rowKey, check.signature);
  }

  flushMonthlyAlertLogCache_(logCache);
}

function evaluateMonthlyFeeAlert_(rowValues, headerMap) {
  const typeRaw = getCellByHeaderVariants_(rowValues, headerMap, COL_MONTHLY_TYPE_NAMES);
  const amountRaw = getCellByHeaderVariants_(rowValues, headerMap, COL_MONTHLY_AMOUNT_NAMES);
  const termRaw = getCellByHeaderVariants_(rowValues, headerMap, COL_MONTHLY_PAYMENT_TERM_NAMES);

  const type = normalizeCompareValue_(typeRaw);
  const term = String(termRaw || "").trim();
  const amountNumber = parseLocalizedNumber_(amountRaw);

  const typeOk = MONTHLY_TRIGGER_TYPES.has(type);
  const amountOk = amountNumber !== null && amountNumber !== 0;
  const termOk = term !== "" && term !== "-";

  const signature = [
    type,
    normalizeCompareValue_(amountRaw),
    normalizeCompareValue_(termRaw)
  ].join("|");

  return {
    shouldSend: typeOk && amountOk && termOk,
    signature
  };
}

function buildMonthlyFeeAlertMessage_(sheet, rowNumber, rowValues, headerMap) {
  const getOne = (name) => getCellByHeaderVariants_(rowValues, headerMap, [name]);

  const type = getCellByHeaderVariants_(rowValues, headerMap, COL_MONTHLY_TYPE_NAMES);
  const amount = getCellByHeaderVariants_(rowValues, headerMap, COL_MONTHLY_AMOUNT_NAMES);
  const term = getCellByHeaderVariants_(rowValues, headerMap, COL_MONTHLY_PAYMENT_TERM_NAMES);

  const link = buildRowLink_(sheet, rowNumber, sheet.getLastColumn());

  return [
    "🚨 *Новый алерт по FF / Setup fee*",
    `*Тип:* ${type}`,
    `*Сумма:* ${amount}`,
    `*Срок оплаты:* ${term}`,
    `*Aff manager:* ${getOne("Aff manager")}`,
    `*Partner:* ${getOne("Partner Name")} (ID: ${getOne("Partner ID")})`,
    `*Campaign ID:* ${getOne("Campaign ID")}`,
    `*GEO:* ${getOne("GEO")}`,
    `*Traffic:* ${getOne("Traffic source campaign")}`,
    `🔗 ${link}`
  ].join("\n");
}

function postToSlackWebhook_(webhookUrl, text) {
  const payload = { text };

  const resp = UrlFetchApp.fetch(webhookUrl, {
    method: "post",
    contentType: "application/json; charset=utf-8",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const code = resp.getResponseCode();
  const body = resp.getContentText();

  if (code < 200 || code >= 300 || (body && body !== "ok")) {
    throw new Error(`Slack webhook error: HTTP ${code} ${body}`);
  }
}

function parseLocalizedNumber_(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return value;

  let s = String(value).trim();
  if (!s) return null;

  s = s.replace(/[\s\u00A0]/g, "");

  if (s.includes(",") && !s.includes(".")) {
    s = s.replace(",", ".");
  } else {
    s = s.replace(/,/g, "");
  }

  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function parseDateValue_(value) {
  if (value === null || value === undefined || value === "") return null;

  const raw = String(value).trim();
  if (!raw) return null;

  const direct = new Date(raw);
  if (!Number.isNaN(direct.getTime())) {
    return direct;
  }

  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const [_, y, m, d] = isoMatch.map(Number);
    const candidate = new Date(Date.UTC(y, m - 1, d));
    if (candidate.getUTCFullYear() === y && candidate.getUTCMonth() === m - 1 && candidate.getUTCDate() === d) {
      return candidate;
    }
    return null;
  }

  const euMatch = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (euMatch) {
    const [_, d, m, y] = euMatch.map(Number);
    const candidate = new Date(Date.UTC(y, m - 1, d));
    if (candidate.getUTCFullYear() === y && candidate.getUTCMonth() === m - 1 && candidate.getUTCDate() === d) {
      return candidate;
    }
  }

  return null;
}

function hasDuplicateUniqueKey_(values) {
  const seen = new Set();
  for (const value of values || []) {
    const normalized = String(value || "").trim();
    if (!normalized) continue;
    if (seen.has(normalized)) return true;
    seen.add(normalized);
  }
  return false;
}

function rangesIntersect_(a, b) {
  const [startA, endA] = a;
  const [startB, endB] = b;
  return startA <= endB && startB <= endA;
}

function escapeSlackText_(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*/g, "\\*")
    .replace(/_/g, "\\_");
}

function normalizeEntityKey_(value) {
  return normalizeHeader_(value)
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/*****************************************
 * СИНК: Monthly Partner's active campaigns -> п/ф SEO Обзорники
 * Новая логика:
 * - строка Monthly получает постоянный unique_key
 * - поиск строки в П/Ф идет сначала по unique_key
 * - старый PFSYNC используется только как fallback для миграции
 *****************************************/
function syncMonthlyRowToPlanFact_(e, monthlySheet) {
  const lastCol = monthlySheet.getLastColumn();
  const headers = monthlySheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);

  const watchedCols = [
    findHeaderIndexByVariants_(headerMap, MONTHLY_UNIQUE_KEY_HEADER_NAMES, false),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.campaignId, true),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.startPeriod, false),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.endPeriod, false),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.feeAmount, true),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.feeType, true),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.dealStatus, true),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.geo, true),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.position, true),
    findHeaderIndexByVariants_(headerMap, MONTHLY_TO_PF_SOURCE_HEADERS.partnerId, true)
  ].filter(Boolean);

  const editedCol = e.range.getColumn();
  if (!watchedCols.includes(editedCol)) return;

  const startRow = e.range.getRow();
  const numRows = e.range.getNumRows();
  if (startRow === 1) return;

  syncMonthlyRowsToPlanFactCore_(monthlySheet, startRow, numRows);
}

function syncMonthlyRowsToPlanFactCore_(monthlySheet, startRow, numRows) {
  if (startRow === 1 || numRows <= 0) return;

  const lastCol = monthlySheet.getLastColumn();
  const headers = monthlySheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);

  const rowsValues = monthlySheet.getRange(startRow, 1, numRows, lastCol).getValues();
  const rowsDisplayValues = monthlySheet.getRange(startRow, 1, numRows, lastCol).getDisplayValues();

  const pfSs = SpreadsheetApp.openById(PF_SPREADSHEET_ID);
  const pfSheet = pfSs.getSheetByName(PF_SHEET_NAME);
  if (!pfSheet) {
    throw new Error(`Не найден лист п/ф: ${PF_SHEET_NAME}`);
  }

  const pfData = pfSheet.getDataRange().getValues();
  if (!pfData.length) {
    throw new Error(`На листе "${PF_SHEET_NAME}" отсутствует строка заголовков`);
  }

  const pfHeaders = pfData[0];
  const pfHeaderMap = buildHeaderMap_(pfHeaders);

  Object.values(PF_HEADERS).forEach(h => {
    findHeaderIndexByVariants_(pfHeaderMap, [h], true);
  });
  findHeaderIndexByVariants_(pfHeaderMap, PF_UNIQUE_KEY_HEADER_NAMES, true);

  const monthlyLogCache = loadMonthlyAlertLogCache_(ensureMonthlyAlertLog_());

  for (let i = 0; i < rowsValues.length; i++) {
    const monthlyRowNumber = startRow + i;
    if (monthlyRowNumber === 1) continue;

    const payload = buildPfPayloadFromMonthlyRow_(
      monthlySheet,
      monthlyRowNumber,
      rowsValues[i],
      rowsDisplayValues[i],
      headerMap
    );
    if (!payload) continue;

    const syncLogKey = makeMonthlyAlertLogKey_("PFSYNC", monthlyRowNumber);

    let targetPfRow = null;

    // 1. Главный поиск: по unique_key в П/Ф
    targetPfRow = findPfRowByUniqueKey_(pfSheet, pfHeaderMap, payload.uniqueKey);

    // 2. Fallback на старый PFSYNC — только для миграции
    if (!targetPfRow) {
      const existingSyncEntry = getMonthlyAlertEntryCached_(monthlyLogCache, syncLogKey);
      if (existingSyncEntry) {
        const parsed = parsePfSyncSignature_(existingSyncEntry.last_signature);
        if (parsed && parsed.pf_row && parsed.pf_row >= 2) {
          const matchedPfRow = resolveSafePfRowByBinding_(
            pfSheet,
            pfHeaderMap,
            parsed.pf_row,
            payload.campaignId,
            payload.partnerId
          );

          if (matchedPfRow) {
            targetPfRow = matchedPfRow;
          }
        }
      }
    }

    // 3. Если не нашли — новая строка
    if (!targetPfRow) {
      targetPfRow = findFirstEmptyPfRow_(pfSheet, pfHeaderMap);
    }

    writePfPayloadToSheetRow_(pfSheet, pfHeaderMap, targetPfRow, payload);

    // 4. Перезаписываем только PFSYNC в новом формате
    upsertMonthlyAlertEntryCached_(
      monthlyLogCache,
      syncLogKey,
      buildPfSyncSignature_(targetPfRow, payload, monthlyRowNumber)
    );
  }

  flushMonthlyAlertLogCache_(monthlyLogCache);
}

function buildPfPayloadFromMonthlyRow_(monthlySheet, rowNumber, rowValues, rowDisplayValues, monthlyHeaderMap) {
  const uniqueKey = getOrCreateMonthlyUniqueKey_(monthlySheet, monthlyHeaderMap, rowNumber, rowValues);

  const campaignId = String(getCellByHeaderVariants_(rowValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.campaignId) || "").trim();
  const partnerId = String(getCellByHeaderVariants_(rowValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.partnerId) || "").trim();
  const feeAmount = getCellByHeaderVariants_(rowValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.feeAmount);
  const feeTypeRaw = String(getCellByHeaderVariants_(rowValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.feeType) || "").trim();
  const dealStatusRaw = String(getCellByHeaderVariants_(rowValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.dealStatus) || "").trim();
  const geo = String(getCellByHeaderVariants_(rowValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.geo) || "").trim();
  const position = String(getCellByHeaderVariants_(rowValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.position) || "").trim();

  const startPeriod = String(getCellByHeaderVariants_(rowDisplayValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.startPeriod) || "").trim();
  const endPeriod = String(getCellByHeaderVariants_(rowDisplayValues, monthlyHeaderMap, MONTHLY_TO_PF_SOURCE_HEADERS.endPeriod) || "").trim();

  const mappedStatus = mapMonthlyDealStatusToPfStatus_(dealStatusRaw);
  const mappedType = mapMonthlyFeeTypeToPfType_(feeTypeRaw);
  const feeAmountFilled = String(feeAmount ?? "").trim() !== "";

  if (!mappedType) return null;

  if (!campaignId || !partnerId || !feeAmountFilled || !mappedStatus || !geo || !position) {
    return null;
  }

  return {
    uniqueKey,
    campaignId,
    partnerId,
    startPeriod,
    endPeriod,
    feeAmount,
    feeType: mappedType,
    feeTypeRaw,
    mappedStatus,
    geo,
    position
  };
}

function writePfPayloadToSheetRow_(pfSheet, pfHeaderMap, rowNumber, payload) {
  const writes = [
    { headerVariants: PF_UNIQUE_KEY_HEADER_NAMES, value: payload.uniqueKey },
    { headerVariants: [PF_HEADERS.sourceId], value: payload.campaignId },
    { headerVariants: [PF_HEADERS.platform], value: PF_PLATFORM_NAME },
    { headerVariants: [PF_HEADERS.feeEuro], value: payload.feeAmount },
    { headerVariants: [PF_HEADERS.type], value: payload.feeType },
    { headerVariants: [PF_HEADERS.status], value: payload.mappedStatus },
    { headerVariants: [PF_HEADERS.geo], value: payload.geo },
    { headerVariants: [PF_HEADERS.position], value: payload.position },
    { headerVariants: [PF_HEADERS.webmasterId], value: payload.partnerId }
  ];

  for (const item of writes) {
    const col = findHeaderIndexByVariants_(pfHeaderMap, item.headerVariants, true);
    pfSheet.getRange(rowNumber, col).setValue(item.value);
  }

  const startCol = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.periodStart], true);
  const endCol = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.periodFinish], true);

  const startRange = pfSheet.getRange(rowNumber, startCol);
  const endRange = pfSheet.getRange(rowNumber, endCol);

  const isPlaced = String(payload.mappedStatus || "").trim().toLowerCase() === "размещены";

  startRange.clearContent();
  endRange.clearContent();

  if (!isPlaced) return;

  const startDate = parseDisplayDateToDateObject_(payload.startPeriod);
  const endDate = parseDisplayDateToDateObject_(payload.endPeriod);

  if (payload.startPeriod && !startDate) {
    throw new Error(`Не удалось распарсить startPeriod: "${payload.startPeriod}" для строки PF ${rowNumber}`);
  }

  if (payload.endPeriod && !endDate) {
    throw new Error(`Не удалось распарсить endPeriod: "${payload.endPeriod}" для строки PF ${rowNumber}`);
  }

  if (startDate) {
    startRange.setValue(startDate);
    startRange.setNumberFormat("dd.MM.yyyy");
  }

  if (endDate) {
    endRange.setValue(endDate);
    endRange.setNumberFormat("dd.MM.yyyy");
  }
}

function parseDisplayDateToDateObject_(value) {
  const s = String(value || "").trim();
  if (!s) return null;

  const m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (!m) return null;

  const day = Number(m[1]);
  const month = Number(m[2]);
  const year = Number(m[3]);

  return new Date(year, month - 1, day, 12, 0, 0);
}

function generateStableUniqueKey_() {
  return Utilities.getUuid();
}

function getOrCreateMonthlyUniqueKey_(monthlySheet, monthlyHeaderMap, rowNumber, rowValues) {
  const uniqueKeyCol = findHeaderIndexByVariants_(monthlyHeaderMap, MONTHLY_UNIQUE_KEY_HEADER_NAMES, true);
  let uniqueKey = String(rowValues[uniqueKeyCol - 1] || "").trim();

  if (!uniqueKey) {
    uniqueKey = generateStableUniqueKey_();
    monthlySheet.getRange(rowNumber, uniqueKeyCol).setValue(uniqueKey);
    rowValues[uniqueKeyCol - 1] = uniqueKey;
  }

  return uniqueKey;
}

function findPfRowByUniqueKey_(pfSheet, pfHeaderMap, uniqueKey) {
  const key = String(uniqueKey || "").trim();
  if (!key) return null;

  const uniqueKeyCol = findHeaderIndexByVariants_(pfHeaderMap, PF_UNIQUE_KEY_HEADER_NAMES, true);
  const lastRow = pfSheet.getLastRow();
  if (lastRow < 2) return null;

  const values = pfSheet.getRange(2, uniqueKeyCol, lastRow - 1, 1).getValues();
  for (let i = 0; i < values.length; i++) {
    if (String(values[i][0] || "").trim() === key) {
      return i + 2;
    }
  }

  return null;
}

function makePfBindingKey_(campaignId, partnerId, monthlyRowNumber) {
  return [
    String(campaignId || "").trim(),
    String(partnerId || "").trim(),
    `ROW${Number(monthlyRowNumber || 0)}`
  ].join("|");
}

// Оставлено для совместимости со старыми версиями лога
function makePfPlacementKey_(payload) {
  return [
    normalizeCompareValue_(payload.campaignId),
    normalizeCompareValue_(payload.partnerId),
    normalizeCompareValue_(payload.startPeriod),
    normalizeCompareValue_(payload.endPeriod),
    normalizeCompareValue_(payload.feeType),
    normalizeCompareValue_(payload.feeAmount),
    normalizeCompareValue_(payload.geo),
    normalizeCompareValue_(payload.position)
  ].join("|");
}

function buildPfSyncSignature_(pfRow, payload, monthlyRowNumber) {
  return JSON.stringify({
    version: 2,
    pf_row: Number(pfRow || 0),
    unique_key: String(payload.uniqueKey || "").trim(),
    campaign_id: String(payload.campaignId || "").trim(),
    partner_id: String(payload.partnerId || "").trim(),
    monthly_row: Number(monthlyRowNumber || 0)
  });
}

function parsePfSyncSignature_(raw) {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

// Оставлено для совместимости со старыми версиями лога
function validatePfSyncBinding_(parsedSignature, placementKey, monthlyRowNumber) {
  if (!parsedSignature) return;

  const actualPlacementKey = String(parsedSignature.placement_key || "").trim();
  const loggedMonthlyRow = Number(parsedSignature.monthly_row || 0);

  if (!actualPlacementKey) {
    return;
  }

  if (loggedMonthlyRow === Number(monthlyRowNumber || 0)) {
    return;
  }

  if (actualPlacementKey !== placementKey) {
    throw new Error(
      `Нарушена привязка PFSYNC для Monthly row ${monthlyRowNumber}. ` +
      `В логе placement_key="${actualPlacementKey}", ` +
      `у текущей строки placement_key="${placementKey}". ` +
      `Запись в П/Ф остановлена, чтобы не перезаписать чужую строку.`
    );
  }
}

// Оставлено для совместимости со старыми версиями лога
function findPfRowByPlacementKeyInLog_(monthlyLogCache, placementKey, currentMonthlyRowNumber) {
  for (const [rowKey, entry] of monthlyLogCache.byKey.entries()) {
    if (!String(rowKey || "").startsWith("PFSYNC|")) continue;

    const parsed = parsePfSyncSignature_(entry.last_signature);
    if (!parsed) continue;

    const parsedPlacementKey = String(parsed.placement_key || "").trim();
    if (!parsedPlacementKey) continue;

    if (parsedPlacementKey !== placementKey) continue;

    if (parsed.pf_row && parsed.pf_row >= 2) {
      return parsed.pf_row;
    }
  }

  return null;
}

function resolveSafePfRowByBinding_(pfSheet, pfHeaderMap, pfRow, campaignId, partnerId) {
  const rowNumber = Number(pfRow || 0);
  if (rowNumber < 2) return null;

  const lastRow = pfSheet.getLastRow();
  const lastCol = pfSheet.getLastColumn();

  if (rowNumber > lastRow) {
    return null;
  }

  const rowValues = pfSheet.getRange(rowNumber, 1, 1, lastCol).getValues()[0];

  const idxSourceId = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.sourceId], true) - 1;
  const idxWebmasterId = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.webmasterId], true) - 1;

  const existingCampaignId = String(rowValues[idxSourceId] || "").trim();
  const existingPartnerId = String(rowValues[idxWebmasterId] || "").trim();

  if (!existingCampaignId && !existingPartnerId) {
    return rowNumber;
  }

  if (
    normalizeCompareValue_(existingCampaignId) === normalizeCompareValue_(campaignId) &&
    normalizeCompareValue_(existingPartnerId) === normalizeCompareValue_(partnerId)
  ) {
    return rowNumber;
  }

  return null;
}

function mapMonthlyDealStatusToPfStatus_(value) {
  const key = normalizeHeader_(value);
  return PF_STATUS_MAP[key] || "";
}

function mapMonthlyFeeTypeToPfType_(value) {
  const normalized = normalizeHeader_(value);
  if (normalized === "ff") return "flat";
  if (normalized === "setup fee") return "setup";
  return "";
}

function findFirstEmptyPfRow_(pfSheet, pfHeaderMap) {
  const lastRow = Math.max(pfSheet.getLastRow(), 2);
  const lastCol = pfSheet.getLastColumn();
  if (lastRow < 2) return 2;

  const data = pfSheet.getRange(2, 1, lastRow - 1, lastCol).getValues();

  const idxSourceId = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.sourceId], true) - 1;
  const idxPlatform = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.platform], true) - 1;
  const idxPeriodStart = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.periodStart], true) - 1;
  const idxPeriodFinish = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.periodFinish], true) - 1;
  const idxFeeEuro = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.feeEuro], true) - 1;
  const idxType = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.type], true) - 1;
  const idxStatus = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.status], true) - 1;
  const idxGeo = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.geo], true) - 1;
  const idxPosition = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.position], true) - 1;
  const idxWebmasterId = findHeaderIndexByVariants_(pfHeaderMap, [PF_HEADERS.webmasterId], true) - 1;

  for (let i = 0; i < data.length; i++) {
    const row = data[i];

    const hasData =
      String(row[idxSourceId] || "").trim() ||
      String(row[idxPlatform] || "").trim() ||
      String(row[idxPeriodStart] || "").trim() ||
      String(row[idxPeriodFinish] || "").trim() ||
      String(row[idxFeeEuro] || "").trim() ||
      String(row[idxType] || "").trim() ||
      String(row[idxStatus] || "").trim() ||
      String(row[idxGeo] || "").trim() ||
      String(row[idxPosition] || "").trim() ||
      String(row[idxWebmasterId] || "").trim();

    if (!hasData) return i + 2;
  }

  return lastRow + 1;
}

/*****************************************
 * ПОИСК ПАРТНЁРОВ -> СТАТИСТИКА ПО НЕДЕЛЯМ
 *****************************************/
function processSearchPartnersStats_(e, sourceSheet) {
  const lastCol = sourceSheet.getLastColumn();
  const headers = sourceSheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);

  const watchedCols = [
    findHeaderIndexByVariants_(headerMap, SEARCH_COL_PARTNER_NAME_NAMES, false),
    findHeaderIndexByVariants_(headerMap, SEARCH_COL_SITE_NAMES, false),
    findHeaderIndexByVariants_(headerMap, SEARCH_COL_CONTACT_NAMES, false),
    findHeaderIndexByVariants_(headerMap, SEARCH_COL_STATUS_NAMES, false),
    findHeaderIndexByVariants_(headerMap, SEARCH_COL_PING_NAMES, false),
    findHeaderIndexByVariants_(headerMap, SEARCH_COL_AFF_MANAGER_NAMES, false)
  ].filter(Boolean);

  if (!watchedCols.length) return;

  const editStartCol = e.range.getColumn();
  const editEndCol = editStartCol + e.range.getNumColumns() - 1;

  const intersectsWatched = watchedCols.some(col => col >= editStartCol && col <= editEndCol);
  if (!intersectsWatched) return;

  const startRow = e.range.getRow();
  const numRows = e.range.getNumRows();
  if (startRow === 1) return;

  const rowsData = sourceSheet.getRange(startRow, 1, numRows, lastCol).getValues();

  const ss = SpreadsheetApp.getActive();
  const statsSheet = ss.getSheetByName(SEARCH_PARTNERS_STATS_SHEET_NAME);
  if (!statsSheet) {
    throw new Error(`Не найден лист: ${SEARCH_PARTNERS_STATS_SHEET_NAME}`);
  }

  const logCache = loadMonthlyAlertLogCache_(ensureMonthlyAlertLog_());
  const period = getSearchWeeklyPeriod_(new Date(), Session.getScriptTimeZone());
  const statsHeaders = statsSheet.getRange(1, 1, 1, statsSheet.getLastColumn()).getValues()[0];
  const statsHeaderMap = buildHeaderMap_(statsHeaders);

  for (let i = 0; i < numRows; i++) {
    const rowNumber = startRow + i;
    if (rowNumber === 1) continue;

    const entity = rowValuesToSearchEntity_(rowsData[i], headerMap);
    const statsRow = ensureSearchStatsPeriodRowByAffManager_(statsSheet, period, entity.affManagerRaw);

    processSearchPartnersRow_(
      entity,
      rowNumber,
      logCache,
      statsSheet,
      statsHeaderMap,
      statsHeaders,
      statsRow
    );
  }

  flushMonthlyAlertLogCache_(logCache);
}

function processSearchPartnersRow_(entity, rowNumber, logCache, statsSheet, statsHeaderMap, statsHeaders, statsRow) {
  if (!entity.entityKey) return;

  const stateKey = makeSearchStateLogKey_(entity.entityKey);
  const existing = getMonthlyAlertEntryCached_(logCache, stateKey);
  const prevState = existing ? parseSearchStateSignature_(existing.last_signature) : null;

  const currentStatusNorm = normalizeCompareValue_(entity.statusRaw);
  const currentPinged = isSearchPingedValue_(entity.pingRaw);
  const currentAffManagerNorm = normalizeCompareValue_(entity.affManagerRaw);

  if (!prevState) {
    incrementSearchOptionalMetric_(statsSheet, statsHeaderMap, statsRow, SEARCH_STATS_COL_NEW_SITES_NAMES);
  }

  if (prevState && !prevState.pinged && currentPinged) {
    incrementSearchOptionalMetric_(statsSheet, statsHeaderMap, statsRow, SEARCH_STATS_COL_PINGED_NAMES);
  }

  if (prevState && prevState.status !== currentStatusNorm && currentStatusNorm) {
    incrementSearchStatusMetric_(statsSheet, statsHeaderMap, statsHeaders, statsRow, entity.statusRaw);
  }

  upsertMonthlyAlertEntryCached_(logCache, stateKey, JSON.stringify({
    entity_key: entity.entityKey,
    site_key: entity.siteKey,
    status: currentStatusNorm,
    pinged: currentPinged,
    aff_manager: currentAffManagerNorm,
    row_number: rowNumber,
    updated_at: new Date().toISOString()
  }));
}

function rowValuesToSearchEntity_(rowValues, headerMap) {
  const partnerNameRaw = String(getCellByHeaderVariants_(rowValues, headerMap, SEARCH_COL_PARTNER_NAME_NAMES) || "").trim();
  const siteRaw = String(getCellByHeaderVariants_(rowValues, headerMap, SEARCH_COL_SITE_NAMES) || "").trim();
  const contactRaw = String(getCellByHeaderVariants_(rowValues, headerMap, SEARCH_COL_CONTACT_NAMES) || "").trim();
  const statusRaw = String(getCellByHeaderVariants_(rowValues, headerMap, SEARCH_COL_STATUS_NAMES) || "").trim();
  const pingRaw = getCellByHeaderVariants_(rowValues, headerMap, SEARCH_COL_PING_NAMES);
  const affManagerRaw = String(getCellByHeaderVariants_(rowValues, headerMap, SEARCH_COL_AFF_MANAGER_NAMES) || "").trim();

  const partnerNameKey = normalizeCompareValue_(partnerNameRaw);
  const siteKey = normalizeSearchSiteKey_(siteRaw);
  const contactKey = normalizeSearchContactKey_(contactRaw);

  let entityKey = "";
  if (partnerNameKey && siteKey) {
    entityKey = `${partnerNameKey}|${siteKey}`;
  } else if (siteKey) {
    entityKey = `site|${siteKey}`;
  } else if (partnerNameKey) {
    entityKey = `partner|${partnerNameKey}`;
  } else if (contactKey) {
    entityKey = `contact|${contactKey}`;
  }

  return {
    entityKey,
    siteKey,
    contactKey,
    partnerNameRaw,
    siteRaw,
    contactRaw,
    statusRaw,
    pingRaw,
    affManagerRaw
  };
}

function normalizeSearchSiteKey_(value) {
  let s = String(value || "").trim().toLowerCase();
  if (!s) return "";

  s = s.replace(/^https?:\/\//, "");
  s = s.replace(/^www\./, "");
  s = s.replace(/\/+$/, "");
  s = s.replace(/\s+/g, "");

  return s;
}

function normalizeSearchContactKey_(value) {
  let s = String(value || "").trim().toLowerCase();
  if (!s) return "";

  s = s.replace(/\s+/g, " ");
  return s;
}

function isSearchPingedValue_(value) {
  if (value === true) return true;

  const s = String(value || "").trim().toLowerCase();
  return s !== "" && s !== "false" && s !== "нет" && s !== "no" && s !== "0" && s !== "-";
}

function makeSearchStateLogKey_(entityKey) {
  return `${SEARCH_STATE_LOG_PREFIX}|${SEARCH_PARTNERS_SHEET_NAME}|${entityKey}`;
}

function parseSearchStateSignature_(raw) {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function getSearchWeeklyPeriod_(dateObj, timezone) {
  const tz = timezone || Session.getScriptTimeZone();
  const localNow = new Date(Utilities.formatDate(dateObj, tz, "yyyy-MM-dd'T'HH:mm:ss"));
  const day = localNow.getDay();

  const diffToThursday = (day - 4 + 7) % 7;

  const start = new Date(localNow);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - diffToThursday);

  const end = new Date(start);
  end.setDate(end.getDate() + 7);

  return {
    start,
    end,
    periodLabel:
      Utilities.formatDate(start, tz, "dd.MM.yyyy") +
      " - " +
      Utilities.formatDate(new Date(end.getTime() - 1), tz, "dd.MM.yyyy")
  };
}

function ensureSearchStatsPeriodRowByAffManager_(statsSheet, period, affManagerRaw) {
  const lastCol = statsSheet.getLastColumn();
  if (lastCol < 1) {
    throw new Error(`На листе "${SEARCH_PARTNERS_STATS_SHEET_NAME}" отсутствуют заголовки`);
  }

  const headers = statsSheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);

  const colPeriod = findHeaderIndexByVariants_(headerMap, SEARCH_STATS_COL_PERIOD_NAMES, true);
  const colAffManager = findHeaderIndexByVariants_(headerMap, SEARCH_STATS_COL_AFF_MANAGER_NAMES, true);

  const affManagerValue = String(affManagerRaw || "").trim();

  const lastRow = Math.max(statsSheet.getLastRow(), 2);
  const data = lastRow >= 2 ? statsSheet.getRange(2, 1, lastRow - 1, lastCol).getValues() : [];

  for (let i = 0; i < data.length; i++) {
    const rowPeriod = String(data[i][colPeriod - 1] || "").trim();
    const rowAffManager = String(data[i][colAffManager - 1] || "").trim();

    if (rowPeriod === period.periodLabel && rowAffManager === affManagerValue) {
      return i + 2;
    }
  }

  const targetRow = findFirstEmptySearchStatsRow_(statsSheet, headerMap);
  statsSheet.getRange(targetRow, colPeriod).setValue(period.periodLabel);
  statsSheet.getRange(targetRow, colAffManager).setValue(affManagerValue);

  return targetRow;
}

function findFirstEmptySearchStatsRow_(statsSheet, headerMap) {
  const lastRow = Math.max(statsSheet.getLastRow(), 2);
  const lastCol = statsSheet.getLastColumn();
  if (lastRow < 2) return 2;

  const colPeriod = findHeaderIndexByVariants_(headerMap, SEARCH_STATS_COL_PERIOD_NAMES, true) - 1;
  const data = statsSheet.getRange(2, 1, lastRow - 1, lastCol).getValues();

  for (let i = 0; i < data.length; i++) {
    if (!String(data[i][colPeriod] || "").trim()) {
      return i + 2;
    }
  }

  return lastRow + 1;
}

function incrementSearchOptionalMetric_(statsSheet, statsHeaderMap, rowNumber, headerVariants) {
  const col = findHeaderIndexByVariants_(statsHeaderMap, headerVariants, false);
  if (!col) return;

  const range = statsSheet.getRange(rowNumber, col);
  const current = Number(range.getValue() || 0);
  range.setValue(current + 1);
}

function incrementSearchStatusMetric_(statsSheet, statsHeaderMap, statsHeaders, rowNumber, statusRaw) {
  const statusNorm = normalizeCompareValue_(statusRaw);
  if (!statusNorm) return;

  const reservedCols = new Set([
    ...SEARCH_STATS_COL_PERIOD_NAMES.map(normalizeHeader_),
    ...SEARCH_STATS_COL_NEW_SITES_NAMES.map(normalizeHeader_),
    ...SEARCH_STATS_COL_PINGED_NAMES.map(normalizeHeader_),
    ...SEARCH_STATS_COL_AFF_MANAGER_NAMES.map(normalizeHeader_)
  ]);

  for (let i = 0; i < statsHeaders.length; i++) {
    const headerRaw = String(statsHeaders[i] || "").trim();
    if (!headerRaw) continue;

    const headerNorm = normalizeHeader_(headerRaw);
    if (reservedCols.has(headerNorm)) continue;

    if (normalizeCompareValue_(headerRaw) !== statusNorm) continue;

    const range = statsSheet.getRange(rowNumber, i + 1);
    const current = Number(range.getValue() || 0);
    range.setValue(current + 1);
    return;
  }
}

/*****************************************
 * СБРОС ЧЕКБОКСОВ "Написали/пинганули"
 *****************************************/
function resetSearchPingCheckboxesForNewPeriod() {
  const ss = SpreadsheetApp.getActive();
  const sourceSheet = ss.getSheetByName(SEARCH_PARTNERS_SHEET_NAME);
  const statsSheet = ss.getSheetByName(SEARCH_PARTNERS_STATS_SHEET_NAME);

  if (!sourceSheet) {
    throw new Error(`Не найден лист: ${SEARCH_PARTNERS_SHEET_NAME}`);
  }
  if (!statsSheet) {
    throw new Error(`Не найден лист: ${SEARCH_PARTNERS_STATS_SHEET_NAME}`);
  }

  const period = getSearchWeeklyPeriod_(new Date(), Session.getScriptTimeZone());

  let statsLastCol = Math.max(statsSheet.getLastColumn(), 1);
  const statsHeaders = statsSheet.getRange(1, 1, 1, statsLastCol).getValues()[0];
  const statsHeaderMap = buildHeaderMap_(statsHeaders);

  let markerCol = findHeaderIndexByVariants_(statsHeaderMap, SEARCH_COL_RESET_MARKER_NAMES, false);

  if (!markerCol) {
    markerCol = statsLastCol + 1;
    statsSheet.getRange(1, markerCol).setValue(SEARCH_COL_RESET_MARKER_NAMES[0]);
  }

  const markerValue = `RESET_DONE|${period.periodLabel}`;
  const markerCell = statsSheet.getRange(2, markerCol);

  if (String(markerCell.getValue() || "").trim() === markerValue) return;

  const sourceLastCol = sourceSheet.getLastColumn();
  if (sourceLastCol < 1) {
    markerCell.setValue(markerValue);
    return;
  }

  const sourceHeaders = sourceSheet.getRange(1, 1, 1, sourceLastCol).getValues()[0];
  const sourceHeaderMap = buildHeaderMap_(sourceHeaders);

  const pingCol = findHeaderIndexByVariants_(sourceHeaderMap, SEARCH_COL_PING_NAMES, true);

  const lastRow = sourceSheet.getLastRow();
  if (lastRow >= 2) {
    const range = sourceSheet.getRange(2, pingCol, lastRow - 1, 1);
    const values = range.getValues();
    const resetValues = values.map(() => [false]);
    range.setValues(resetValues);

    const logCache = loadMonthlyAlertLogCache_(ensureMonthlyAlertLog_());
    const rowsData = sourceSheet.getRange(2, 1, lastRow - 1, sourceLastCol).getValues();

    for (let i = 0; i < rowsData.length; i++) {
      const rowNumber = i + 2;
      const entity = rowValuesToSearchEntity_(rowsData[i], sourceHeaderMap);
      if (!entity.entityKey) continue;

      const stateKey = makeSearchStateLogKey_(entity.entityKey);
      const existing = getMonthlyAlertEntryCached_(logCache, stateKey);
      if (!existing) continue;

      const prevState = parseSearchStateSignature_(existing.last_signature);
      if (!prevState) continue;

      prevState.pinged = false;
      prevState.updated_at = new Date().toISOString();
      prevState.row_number = rowNumber;

      upsertMonthlyAlertEntryCached_(logCache, stateKey, JSON.stringify(prevState));
    }

    flushMonthlyAlertLogCache_(logCache);
  }

  markerCell.setValue(markerValue);
  Logger.log(`Checkbox reset completed for period: ${period.periodLabel}`);
}

/*****************************************
 * ИНИЦИАЛИЗАЦИЯ БАЗЫ ДЛЯ "ПОИСК ПАРТНЁРОВ"
 *****************************************/
function initSearchPartnersStatsBaseline() {
  const ss = SpreadsheetApp.getActive();
  const sourceSheet = ss.getSheetByName(SEARCH_PARTNERS_SHEET_NAME);
  const statsSheet = ss.getSheetByName(SEARCH_PARTNERS_STATS_SHEET_NAME);

  if (!sourceSheet) throw new Error(`Не найден лист: ${SEARCH_PARTNERS_SHEET_NAME}`);
  if (!statsSheet) throw new Error(`Не найден лист: ${SEARCH_PARTNERS_STATS_SHEET_NAME}`);

  const lastCol = sourceSheet.getLastColumn();
  const lastRow = sourceSheet.getLastRow();
  if (lastRow < 2) {
    Logger.log("На листе 'Поиск партнёров' нет данных для инициализации");
    return;
  }

  const headers = sourceSheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);
  const data = sourceSheet.getRange(2, 1, lastRow - 1, lastCol).getValues();

  const logCache = loadMonthlyAlertLogCache_(ensureMonthlyAlertLog_());

  for (let i = 0; i < data.length; i++) {
    const rowNumber = i + 2;
    const entity = rowValuesToSearchEntity_(data[i], headerMap);
    if (!entity.entityKey) continue;

    upsertMonthlyAlertEntryCached_(logCache, makeSearchStateLogKey_(entity.entityKey), JSON.stringify({
      entity_key: entity.entityKey,
      site_key: entity.siteKey,
      status: normalizeCompareValue_(entity.statusRaw),
      pinged: isSearchPingedValue_(entity.pingRaw),
      aff_manager: normalizeCompareValue_(entity.affManagerRaw),
      row_number: rowNumber,
      updated_at: new Date().toISOString()
    }));
  }

  flushMonthlyAlertLogCache_(logCache);

  const period = getSearchWeeklyPeriod_(new Date(), Session.getScriptTimeZone());

  const uniqueManagers = new Set();
  for (let i = 0; i < data.length; i++) {
    const entity = rowValuesToSearchEntity_(data[i], headerMap);
    const manager = String(entity.affManagerRaw || "").trim();
    uniqueManagers.add(manager);
  }

  for (const manager of uniqueManagers) {
    ensureSearchStatsPeriodRowByAffManager_(statsSheet, period, manager);
  }

  Logger.log("initSearchPartnersStatsBaseline выполнен");
}

/***************
 * SLACKLOG КЭШ
 ***************/
function ensureSlackLog_() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(SLACKLOG_SHEET_NAME);
  if (sh) return sh;

  try {
    sh = ss.insertSheet(SLACKLOG_SHEET_NAME);
    sh.getRange(1, 1, 1, 7).setValues([[
      "key",
      "thread_ts",
      "last_status",
      "onapproval_count",
      "analyst_info_hash",
      "last_onapproval_sig",
      "last_onapproval_at"
    ]]);
    sh.hideSheet();
    return sh;
  } catch (err) {
    sh = ss.getSheetByName(SLACKLOG_SHEET_NAME);
    if (sh) return sh;
    throw err;
  }
}

function loadSlackLogCache_(logSheet) {
  const lastRow = logSheet.getLastRow();
  const rows = lastRow >= 2 ? logSheet.getRange(2, 1, lastRow - 1, 7).getValues() : [];

  const byKey = new Map();
  for (let i = 0; i < rows.length; i++) {
    const rowNum = i + 2;
    const key = String(rows[i][0] || "").trim();
    if (!key) continue;

    byKey.set(key, {
      row: rowNum,
      key,
      thread_ts: String(rows[i][1] || "").trim(),
      last_status: String(rows[i][2] || "").trim(),
      onapproval_count: Number(rows[i][3] || 0),
      analyst_info_hash: String(rows[i][4] || "").trim(),
      last_onapproval_sig: String(rows[i][5] || "").trim(),
      last_onapproval_at: String(rows[i][6] || "").trim()
    });
  }

  return {
    sheet: logSheet,
    byKey,
    nextRow: Math.max(lastRow + 1, 2),
    pendingRows: new Map(),
    clearedRows: new Set()
  };
}

function getLogEntryCached_(logCache, key) {
  return logCache.byKey.get(key) || null;
}

function upsertLogEntryCached_(logCache, key, data) {
  const entry = getLogEntryCached_(logCache, key);
  const row = entry ? entry.row : logCache.nextRow++;

  const newEntry = {
    row,
    key,
    thread_ts: data.thread_ts ?? (entry?.thread_ts || ""),
    last_status: data.last_status ?? (entry?.last_status || ""),
    onapproval_count: data.onapproval_count ?? (entry?.onapproval_count || 0),
    analyst_info_hash: data.analyst_info_hash ?? (entry?.analyst_info_hash || ""),
    last_onapproval_sig: data.last_onapproval_sig ?? (entry?.last_onapproval_sig || ""),
    last_onapproval_at: data.last_onapproval_at ?? (entry?.last_onapproval_at || "")
  };

  logCache.byKey.set(key, newEntry);
  logCache.pendingRows.set(row, [
    newEntry.key,
    newEntry.thread_ts,
    newEntry.last_status,
    newEntry.onapproval_count,
    newEntry.analyst_info_hash,
    newEntry.last_onapproval_sig,
    newEntry.last_onapproval_at
  ]);
  logCache.clearedRows.delete(row);
}

function deleteLogEntryCached_(logCache, key) {
  const entry = getLogEntryCached_(logCache, key);
  if (!entry) return;

  logCache.byKey.delete(key);
  logCache.pendingRows.delete(entry.row);
  logCache.clearedRows.add(entry.row);
}

function flushSlackLogCache_(logCache) {
  if (!logCache) return;

  if (logCache.clearedRows.size > 0) {
    for (const row of Array.from(logCache.clearedRows).sort((a, b) => a - b)) {
      logCache.sheet.getRange(row, 1, 1, 7).clearContent();
    }
    logCache.clearedRows.clear();
  }

  if (logCache.pendingRows.size > 0) {
    const rows = Array.from(logCache.pendingRows.keys()).sort((a, b) => a - b);
    for (const row of rows) {
      logCache.sheet.getRange(row, 1, 1, 7).setValues([logCache.pendingRows.get(row)]);
    }
    logCache.pendingRows.clear();
  }
}

/***************
 * НОРМАЛИЗАЦИЯ / HASH / HTTP / REACTIONS
 ***************/
function normalizeThreadTs_(v) {
  let s = String(v ?? "").trim();
  if (!s) return "";

  s = s.replace(/\s+/g, "");

  if (s.includes(".")) return s;

  if (/^\d{13,}$/.test(s)) {
    return s.slice(0, -6) + "." + s.slice(-6);
  }

  return s;
}

function hashText_(text) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, text, Utilities.Charset.UTF_8);
  return bytes.map(b => ("0" + (b & 0xFF).toString(16)).slice(-2)).join("");
}

function withRetries_(fn, opts = {}) {
  const retries = opts.retries ?? 5;
  const baseSleep = opts.baseSleep ?? 450;
  const maxSleep = opts.maxSleep ?? 5000;

  let lastErr;
  for (let i = 0; i <= retries; i++) {
    try {
      return fn(i);
    } catch (err) {
      lastErr = err;
      Utilities.sleep(Math.min(maxSleep, baseSleep * Math.pow(2, i)));
    }
  }
  throw lastErr;
}

function fetchSlack_(url, payloadObj) {
  const token = getProp_("SLACK_BOT_TOKEN");

  return withRetries_(() => {
    const resp = UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json; charset=utf-8",
      headers: { Authorization: `Bearer ${token}` },
      payload: JSON.stringify(payloadObj),
      muteHttpExceptions: true
    });

    const status = resp.getResponseCode();
    const headers = resp.getAllHeaders ? resp.getAllHeaders() : {};
    const bodyText = resp.getContentText();

    if (status >= 500) throw new Error(`Slack HTTP ${status}: ${bodyText}`);

    let data;
    try {
      data = JSON.parse(bodyText);
    } catch (e) {
      throw new Error(`Slack bad JSON (HTTP ${status}): ${bodyText}`);
    }

    if (!data.ok && data.error === "rate_limited") {
      const retryAfter = Number(headers["Retry-After"] || headers["retry-after"] || 1);
      Utilities.sleep(Math.min(10000, Math.max(1000, retryAfter * 1000)));
      throw new Error("Slack rate_limited");
    }

    if (status === 429) {
      const retryAfter = Number(headers["Retry-After"] || headers["retry-after"] || 2);
      Utilities.sleep(Math.min(10000, Math.max(1000, retryAfter * 1000)));
      throw new Error("Slack HTTP 429");
    }

    return data;
  }, { retries: 5, baseSleep: 450, maxSleep: 5000 });
}

function removeManagedReactions_(channel, timestamp) {
  for (const name of MANAGED_REACTIONS) {
    try {
      slackRemoveReaction_(channel, timestamp, name);
    } catch (err) {
      Logger.log(`removeReaction(${name}) error: ${err}`);
    }
  }
}

function slackAddReaction_(channel, timestamp, emojiName) {
  const url = "https://slack.com/api/reactions.add";
  const data = fetchSlack_(url, { channel, timestamp, name: emojiName });

  if (!data.ok && data.error !== "already_reacted") {
    throw new Error(`Slack reaction add error: ${data.error}`);
  }
  return data;
}

function slackRemoveReaction_(channel, timestamp, emojiName) {
  const url = "https://slack.com/api/reactions.remove";
  const data = fetchSlack_(url, { channel, timestamp, name: emojiName });

  const okErrors = new Set(["no_reaction", "not_reacted"]);
  if (!data.ok && !okErrors.has(data.error)) {
    throw new Error(`Slack reaction remove error: ${data.error}`);
  }
  return data;
}

/***************
 * ССЫЛКА НА СТРОКУ
 ***************/
function buildRowLink_(sheet, row, lastColumn) {
  const ss = SpreadsheetApp.getActive();
  const spreadsheetId = ss.getId();
  const gid = sheet.getSheetId();

  const a1Start = `A${row}`;
  const endColLetter = columnToLetter_(Math.max(1, lastColumn));
  const a1End = `${endColLetter}${row}`;

  const range = `${a1Start}:${a1End}`;
  const url = `https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit#gid=${gid}&range=${encodeURIComponent(range)}`;
  return `<${url}|Открыть строку ${row}>`;
}

function columnToLetter_(column) {
  let temp = column;
  let letter = "";
  while (temp > 0) {
    const mod = (temp - 1) % 26;
    letter = String.fromCharCode(65 + mod) + letter;
    temp = Math.floor((temp - mod) / 26);
  }
  return letter;
}

/***************
 * СООБЩЕНИЯ
 ***************/
function buildOnApprovalMessage_(headers, rowValues, rowNumber, isRepeat) {
  const headerMap = buildHeaderMap_(headers);
  const get = (name) => {
    const idx = headerMap[normalizeHeader_(name)];
    return idx ? rowValues[idx - 1] : "";
  };

  const repeatTag = isRepeat ? " 🔁 *повторно*" : "";

  return [
    `🟡 *Заявка на апрув* — статус: *${ON_APPROVAL_VALUE}*${repeatTag} (строка ${rowNumber})`,
    `*Aff manager:* ${get("Aff manager")}`,
    `*Partner:* ${get("Partner Name")} (ID: ${get("Partner ID")})`,
    `*Traffic:* ${get("Traffic source campaign")}`,
    `*GEO:* ${get("GEO")}`,
    `*Period:* ${get("Deal period")}`,
    `*Type:* ${get("Deal type")}`,
    `*Terms:* ${get("Deal's terms")}`,
    `*Possible FTDs:* ${get("Possible amount of FTDs")}`,
    `*Total payment:* ${get("Примерный Total payment")}`,
    `*Campaign ID:* ${get("Campaign ID")}`,
    `*Доп инфа:* ${get("Доп инфа")}`
  ].join("\n");
}

/***************
 * SLACK API
 ***************/
function slackPostMessage_(payload) {
  const url = "https://slack.com/api/chat.postMessage";
  const data = fetchSlack_(url, payload);
  if (!data.ok) throw new Error(`Slack API error: ${data.error}`);
  return data;
}

function getProp_(key) {
  const v = PropertiesService.getScriptProperties().getProperty(key);
  if (!v) throw new Error(`Script property не задан: ${key}`);
  return v;
}

/***************
 * МИГРАЦИЯ НА unique_key
 ***************/
function migrateExistingMonthlyPlanFactBindingsToUniqueKey_() {
  const ss = SpreadsheetApp.getActive();
  const monthlySheet = ss.getSheetByName(TARGET_ACTIVE_SHEET_NAME);
  if (!monthlySheet) {
    throw new Error(`Не найден лист: ${TARGET_ACTIVE_SHEET_NAME}`);
  }

  const lastRow = monthlySheet.getLastRow();
  if (lastRow < 2) {
    Logger.log("Нет строк для миграции");
    return;
  }

  syncMonthlyRowsToPlanFactCore_(monthlySheet, 2, lastRow - 1);
  Logger.log(`Миграция на unique_key завершена. Обработано строк: ${lastRow - 1}`);
}

function runMigrationToUniqueKey() {
  migrateExistingMonthlyPlanFactBindingsToUniqueKey_();
}

/***************
 * ТЕСТЫ / ДЕБАГ
 ***************/
function testSlack() {
  const res = slackPostMessage_({
    channel: getProp_("SLACK_CHANNEL"),
    text: "✅ testSlack: сообщение из Apps Script"
  });
  Logger.log(res);
}

function testAppendApprovedRow(rowNumber) {
  rowNumber = rowNumber || 58;

  const ss = SpreadsheetApp.getActive();
  const sourceSheet = ss.getSheetByName(SHEET_NAME);
  if (!sourceSheet) throw new Error(`Не найден лист: ${SHEET_NAME}`);
  if (rowNumber < 2) throw new Error("Номер строки должен быть >= 2");

  const lastCol = sourceSheet.getLastColumn();
  const headers = sourceSheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);
  const rowValues = sourceSheet.getRange(rowNumber, 1, 1, lastCol).getValues()[0];

  const ctx = buildRuntimeContext_(sourceSheet, headers, headerMap);
  appendApprovedDealToActiveCampaignsCached_(ctx, rowValues);
  flushActiveCache_(ctx.activeCache);

  Logger.log(`Строка ${rowNumber} обработана для переноса в "${TARGET_ACTIVE_SHEET_NAME}"`);
}

function debugHeaders() {
  const sh = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  if (!sh) throw new Error(`Не найден лист: ${SHEET_NAME}`);
  const headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  Logger.log(headers.map(h => `[${h}]`).join(" | "));
}

function debugTargetHeaders() {
  const sh = SpreadsheetApp.getActive().getSheetByName(TARGET_ACTIVE_SHEET_NAME);
  if (!sh) throw new Error(`Не найден лист: ${TARGET_ACTIVE_SHEET_NAME}`);
  const headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  Logger.log(headers.map(h => `[${h}]`).join(" | "));
}

function testSyncMonthlyRowToPlanFact(rowNumber) {
  rowNumber = rowNumber || 2;

  const monthlySheet = SpreadsheetApp.getActive().getSheetByName(TARGET_ACTIVE_SHEET_NAME);
  if (!monthlySheet) throw new Error(`Не найден лист: ${TARGET_ACTIVE_SHEET_NAME}`);

  const lastCol = monthlySheet.getLastColumn();
  const headers = monthlySheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);
  const rowValues = monthlySheet.getRange(rowNumber, 1, 1, lastCol).getValues()[0];
  const rowDisplayValues = monthlySheet.getRange(rowNumber, 1, 1, lastCol).getDisplayValues()[0];

  const payload = buildPfPayloadFromMonthlyRow_(monthlySheet, rowNumber, rowValues, rowDisplayValues, headerMap);
  Logger.log(JSON.stringify(payload, null, 2));
}

function testRunMonthlyToPfSync(rowNumber) {
  rowNumber = rowNumber || 2;

  const monthlySheet = SpreadsheetApp.getActive().getSheetByName(TARGET_ACTIVE_SHEET_NAME);
  if (!monthlySheet) throw new Error(`Не найден лист: ${TARGET_ACTIVE_SHEET_NAME}`);

  const lastCol = monthlySheet.getLastColumn();
  const headers = monthlySheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const headerMap = buildHeaderMap_(headers);

  const watchedCol = findHeaderIndexByVariants_(
    headerMap,
    MONTHLY_TO_PF_SOURCE_HEADERS.campaignId,
    true
  );

  const fakeEvent = {
    source: SpreadsheetApp.getActive(),
    range: monthlySheet.getRange(rowNumber, watchedCol)
  };

  syncMonthlyRowToPlanFact_(fakeEvent, monthlySheet);
  Logger.log(`Forced sync done for row ${rowNumber}`);
}

function testRunMonthlyToPfSync307() {
  testRunMonthlyToPfSync(307);
}

function testRunAffiliateManagerSync() {
  runFullAffiliateManagerSync();
}
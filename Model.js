.pragma library

function parseStatus(text) {
  try {
    var data = JSON.parse(String(text || ""))
    return data && typeof data === "object" ? data : {}
  } catch (e) {
    return {}
  }
}

function gitDiff(inserted, deleted) {
  return "+" + Number(inserted || 0) + " −" + Number(deleted || 0)
}

function gitDiffSparse(inserted, deleted) {
  var ins = Number(inserted || 0)
  var del = Number(deleted || 0)
  if (del > 0) return "+" + ins + " −" + del
  return "+" + ins
}

function charDiffParens(inserted, deleted) {
  return "(" + gitDiffSparse(inserted, deleted) + ")"
}

function statsDigits(rows) {
  var plus = 1
  var minus = 0
  var words = 1
  for (var i = 0; i < (rows || []).length; i++) {
    var p = String(Math.max(0, Math.round(Number(rows[i].inserted_chars || 0)))).length
    var d = Number(rows[i].deleted_chars || 0)
    var m = String(Math.max(0, Math.round(d))).length
    var w = String(Math.max(0, Math.round(Number(rows[i].net_words || 0)))).length
    if (p > plus) plus = p
    if (d > 0 && m > minus) minus = m
    if (w > words) words = w
  }
  return { plus: plus, minus: minus, words: words }
}

function seriesFor(sparkline, name) {
  var found = seriesByName(sparkline, name)
  if (!found) return null
  return { index: Number(found.index || 0), focused: found.focused === true }
}

function seriesByName(sparkline, name) {
  var series = (sparkline && sparkline.series) ? sparkline.series : []
  var needle = String(name || "")
  for (var i = 0; i < series.length; i++) {
    if (String(series[i].app_class || "") === needle) return series[i]
  }
  return null
}

function seriesPeak(points) {
  var max = 0
  for (var i = 0; i < (points || []).length; i++) {
    var n = Number(points[i] || 0)
    if (n > max) max = n
  }
  return max
}

function rowName(row) {
  if (!row) return ""
  return String(row.name || row.app_class || "")
}

var CLASS_LABELS = {
  "md.obsidian.Obsidian": "Obsidian",
  obsidian: "Obsidian",
  "grok-bot": "Grok Bot",
  chromium: "Other",
  "chromium-browser": "Other",
  "google-chrome": "Other",
  "google-chrome-stable": "Other",
  "brave-browser": "Other",
  brave: "Other",
  firefox: "Other",
  "firefox-esr": "Other",
  foot: "Foot",
  Alacritty: "Alacritty",
  alacritty: "Alacritty",
  kitty: "Kitty",
  ghostty: "Ghostty",
  "com.mitchellh.ghostty": "Ghostty",
  "org.wezfurlong.wezterm": "WezTerm",
  code: "Code",
  Code: "Code",
  slack: "Slack",
  herdr: "Herdr"
}

var AGENT_LABELS = {
  grok: "Grok",
  claude: "Claude",
  codex: "Codex",
  gemini: "Gemini",
  chatgpt: "ChatGPT",
  cursor: "Cursor",
  copilot: "Copilot",
  amp: "Amp",
  opencode: "OpenCode",
  windsurf: "Windsurf"
}

var CLASS_AI = {
  "grok-bot": "Grok",
  Claude: "Claude",
  claude: "Claude",
  "claude-desktop": "Claude",
  "codex-desktop": "Codex",
  codex: "Codex",
  Cursor: "Cursor",
  cursor: "Cursor",
  windsurf: "Windsurf"
}

var SITE_AI = {
  chatgpt: "ChatGPT",
  grok: "Grok",
  claude: "Claude"
}

var SITE_LABELS = {
  x: "X",
  twitter: "X",
  github: "GitHub",
  google: "Google",
  youtube: "YouTube",
  gmail: "Gmail",
  reddit: "Reddit",
  linkedin: "LinkedIn",
  bluesky: "Bluesky",
  chatgpt: "ChatGPT",
  grok: "Grok",
  wikipedia: "Wikipedia",
  stackoverflow: "Stack Overflow",
  notion: "Notion",
  linear: "Linear",
  slack: "Slack"
}

// JetBrainsMono Nerd Font (same set as weather, audio, wifi).
var ICON_WORDS = "󰧮" // nf-md-file-document-outline
var ICON_GOAL = "󰓾" // nf-md-target

var BROWSER_LEFT = {
  chromium: true,
  "chromium-browser": true,
  "google-chrome": true,
  "google-chrome-stable": true,
  "brave-browser": true,
  brave: true,
  firefox: true,
  "firefox-esr": true,
  librewolf: true,
  vivaldi: true,
  "vivaldi-stable": true
}

function titleCaseWords(text) {
  return String(text || "").replace(/[-_]+/g, " ").replace(/\b([a-z])/g, function(_m, c) {
    return c.toUpperCase()
  })
}

function displayName(name) {
  name = String(name || "")
  if (!name) return ""
  if (CLASS_LABELS[name]) return CLASS_LABELS[name]
  if (name.indexOf(" · ") >= 0) {
    var parts = name.split(" · ")
    var left = parts[0]
    var right = parts.slice(1).join(" · ")
    var site = SITE_LABELS[right.toLowerCase()]
    if (site && BROWSER_LEFT[left]) return site
    if (AGENT_LABELS[left.toLowerCase()] || left === "herdr") return right
    var leftLabel = CLASS_LABELS[left] || titleCaseWords(left)
    return leftLabel + " · " + right
  }
  if (name.indexOf(".") >= 0) {
    var last = name.split(".").pop()
    return CLASS_LABELS[last] || titleCaseWords(last)
  }
  return titleCaseWords(name)
}

function aiTool(name) {
  name = String(name || "")
  if (!name) return ""
  if (CLASS_AI[name]) return CLASS_AI[name]
  if (name.indexOf(" · ") >= 0) {
    var left = name.split(" · ")[0]
    var right = name.split(" · ").slice(1).join(" · ")
    if (AGENT_LABELS[left.toLowerCase()]) return AGENT_LABELS[left.toLowerCase()]
    if (SITE_AI[right.toLowerCase()]) return SITE_AI[right.toLowerCase()]
  }
  return SITE_AI[name.toLowerCase()] || ""
}

function rowTool(name) {
  var tool = aiTool(name)
  if (!tool) return ""
  var shown = displayName(name)
  if (shown === tool || shown.toLowerCase().indexOf(tool.toLowerCase()) === 0)
    return ""
  return tool
}

function matchLabel(match) {
  match = String(match || "")
  if (match === "all" || match === "*") return "Everything"
  if (match.indexOf("site:") === 0) return displayName("chromium · " + match.substring(5))
  if (match.indexOf("class:") === 0) return sourceAppLabel(match.substring(6))
  if (match.indexOf("herdr:") === 0) return match.substring(6)
  if (match.indexOf("activity:") === 0) return displayName(match.substring(9))
  if (match.indexOf("ws:") === 0) return "ws " + match.substring(3)
  if (match.indexOf("workspace:") === 0) return "ws " + match.substring(10)
  return sourceAppLabel(match)
}

function sourceAppLabel(klass) {
  klass = String(klass || "")
  if (BROWSER_LEFT[klass]) return "Chromium"
  var label = displayName(klass)
  if (label === "Other") return "Chromium"
  return label
}

function matchIdentity(match) {
  match = String(match || "").trim()
  if (!match) return ""
  var lower = match.toLowerCase()
  if (lower === "all" || lower === "*") return "all"
  if (lower.indexOf("site:") === 0) return "site:" + match.substring(5).toLowerCase()
  if (lower.indexOf("herdr:") === 0) return "herdr:" + match.substring(6).toLowerCase()
  if (lower.indexOf("ws:") === 0) return "ws:" + match.substring(3).toLowerCase()
  if (lower.indexOf("workspace:") === 0) return "ws:" + match.substring(10).toLowerCase()
  var value = match
  if (lower.indexOf("class:") === 0) value = match.substring(6)
  else if (lower.indexOf("activity:") === 0) {
    value = match.substring(9)
    var bits = value.split(" · ")
    if (bits.length > 1 && BROWSER_LEFT[bits[0]])
      return "site:" + bits.slice(1).join(" · ").toLowerCase()
    if (bits.length > 1 && (bits[0] === "herdr" || AGENT_LABELS[bits[0].toLowerCase()]))
      return "herdr:" + bits.slice(1).join(" · ").toLowerCase()
  }
  var short = String(value).split(".").pop()
  return "app:" + String(short || value).toLowerCase()
}

function matchCovered(matches, match) {
  var id = matchIdentity(match)
  if (!id) return false
  var list = matches || []
  for (var i = 0; i < list.length; i++) {
    if (matchIdentity(list[i]) === id) return true
  }
  return false
}

function canonicalGoalMatch(name, appClass) {
  name = String(name || "")
  appClass = String(appClass || "")
  if (!name && !appClass) return ""
  var bits = name.split(" · ")
  var left = bits[0]
  var right = bits.slice(1).join(" · ")
  if (right && BROWSER_LEFT[left]) return "site:" + right
  if (right && (left === "herdr" || AGENT_LABELS[left.toLowerCase()])) return "herdr:" + right
  if (appClass) return "class:" + appClass
  if (BROWSER_LEFT[name]) return "class:" + name
  return name ? "class:" + name : ""
}

function goalMatches(goal) {
  if (!goal) return []
  if (goal.matches && goal.matches.length) return goal.matches
  var match = goal.match
  if (match && match.length !== undefined && typeof match !== "string") return match
  return match ? [String(match)] : []
}

function goalSourceOptions(status) {
  var out = []
  var seen = {}
  function add(match, hint) {
    match = String(match || "")
    var id = matchIdentity(match)
    if (!match || !id || id === "app:unknown" || seen[id]) return
    seen[id] = true
    out.push({ match: match, label: matchLabel(match), hint: hint || "" })
  }
  status = status || {}
  var site = status.active_site || ""
  var herdr = status.active_herdr_workspace || ""
  var act = status.active_activity || ""
  var klass = status.active_class || ""
  if (site) add("site:" + site, "this window")
  else if (herdr) add("herdr:" + herdr, "this window")
  else if (klass) add("class:" + klass, "this window")
  else if (act) add(canonicalGoalMatch(act, klass), "this window")
  var list = status.activities || []
  var i
  for (i = 0; i < list.length; i++) {
    add(canonicalGoalMatch(rowName(list[i]), list[i].app_class || ""), "")
  }
  var sites = status.sites || []
  for (i = 0; i < sites.length; i++) add("site:" + sites[i].name, "")
  var herdrs = status.herdr_workspaces || []
  for (i = 0; i < herdrs.length; i++) add("herdr:" + herdrs[i].name, "")
  var apps = status.apps || []
  for (i = 0; i < apps.length; i++) add("class:" + apps[i].app_class, "")
  add("all", "")
  return out
}

function visibleActivities(rows, focused, solo, limit) {
  limit = Math.max(1, Number(limit || 10))
  rows = rows || []
  if (rows.length <= limit) return rows.slice()
  var out = rows.slice(0, limit)
  var seen = {}
  var i
  for (i = 0; i < out.length; i++) seen[rowName(out[i])] = true
  function pin(name) {
    name = String(name || "")
    if (!name || seen[name]) return
    for (var r = 0; r < rows.length; r++) {
      if (rowName(rows[r]) !== name) continue
      out.pop()
      out.push(rows[r])
      seen[name] = true
      return
    }
  }
  pin(focused)
  pin(solo)
  return out
}

function goalList(status) {
  var src = []
  if (status && status.goals && status.goals.length) src = status.goals
  else if (status && status.goal) src = [status.goal]
  var out = []
  for (var i = 0; i < src.length; i++) {
    var g = src[i] || {}
    out.push({
      label: g.label || "",
      match: g.match,
      matches: goalMatches(g).slice(),
      target: Number(g.target || 0),
      net_words: Number(g.net_words || 0),
      percent: Number(g.percent || 0)
    })
  }
  return out
}

function cloneDraftGoals(goals) {
  var src = goals || []
  var out = []
  for (var i = 0; i < src.length; i++) {
    out.push({
      label: src[i].label || "",
      target: Number(src[i].target || 0),
      matches: goalMatches(src[i]).slice(),
      net_words: src[i].net_words,
      percent: src[i].percent
    })
  }
  return out
}

function goalsPayload(draftGoals) {
  var payload = []
  var list = draftGoals || []
  for (var i = 0; i < list.length; i++) {
    var m = list[i].matches || []
    if (!m.length) continue
    payload.push({
      match: m.length === 1 ? m[0] : m,
      words: Number(list[i].target || 0),
      label: list[i].label || matchLabel(m[0])
    })
  }
  return payload
}

function goalCanAccept(goal) {
  if (!goal) return false
  return (goal.matches || []).length > 0
}

function clampIndex(i, n) {
  n = Number(n || 0)
  if (n <= 0) return -1
  i = Number(i)
  if (isNaN(i)) return 0
  if (i < 0) return 0
  if (i >= n) return n - 1
  return i
}

function emptyEditorState() {
  return { open: false, selected: -1, editing: -1, fieldFocused: false }
}

function openEditorState(count) {
  count = Number(count || 0)
  return {
    open: true,
    selected: count > 0 ? 0 : -1,
    editing: -1,
    fieldFocused: false
  }
}

function closeEditorState() {
  return { open: false, selected: -1, editing: -1, fieldFocused: false }
}

function applyGoalsCommand(state, command, count, index) {
  state = state || emptyEditorState()
  count = Number(count || 0)
  command = String(command || "")
  var selected = clampIndex(state.selected, count)

  if (command === "done" || command === "close") {
    if (!state.open) return { state: closeEditorState(), action: "none" }
    return { state: closeEditorState(), action: "close" }
  }
  if (command === "open") {
    if (state.open) return { state: state, action: "none" }
    return { state: openEditorState(count), action: "open" }
  }
  if (command === "g") {
    if (state.fieldFocused) return { state: state, action: "none" }
    if (state.open) return { state: closeEditorState(), action: "close" }
    return { state: openEditorState(count), action: "open" }
  }
  if (command === "escape") {
    if (!state.open) return { state: state, action: "none" }
    return { state: closeEditorState(), action: "close" }
  }
  if (!state.open) return { state: state, action: "none" }
  if (command === "accept" || command === "enter" || command === "return") {
    if (state.editing < 0) return { state: state, action: "none" }
    var accepted = clampIndex(state.editing, count)
    return {
      state: { open: true, selected: accepted, editing: -1, fieldFocused: false },
      action: "accept"
    }
  }
  if (command === "click") {
    var clicked = clampIndex(index, count)
    if (clicked < 0) return { state: state, action: "none" }
    return {
      state: { open: true, selected: clicked, editing: clicked, fieldFocused: false },
      action: "edit"
    }
  }
  if (command === "edit") {
    if (selected < 0) return { state: state, action: "none" }
    return {
      state: { open: true, selected: selected, editing: selected, fieldFocused: false },
      action: "edit"
    }
  }
  if (command === "up") {
    var up = clampIndex(selected < 0 ? 0 : selected - 1, count)
    return {
      state: { open: true, selected: up, editing: -1, fieldFocused: false },
      action: "select"
    }
  }
  if (command === "down") {
    var down = clampIndex(selected < 0 ? 0 : selected + 1, count)
    return {
      state: { open: true, selected: down, editing: -1, fieldFocused: false },
      action: "select"
    }
  }
  return { state: state, action: "none" }
}

function emptyStatus() {
  return {
    state: "starting",
    message: "Starting…",
    paused: false,
    today_words: 0,
    live_wpm: 0,
    last_burst_wpm: 0,
    session_wpm: 0,
    active_class: "",
    active_title: "",
    active_activity: "",
    active_hypr_workspace: "",
    active_herdr_workspace: "",
    active_site: "",
    goal: { app_class: "obsidian", match: "obsidian", label: "obsidian", target: 1000, net_words: 0, inserted_words: 0, deleted_words: 0, percent: 0 },
    goals: [],
    apps: [],
    activities: [],
    hypr_workspaces: [],
    herdr_workspaces: [],
    sites: [],
    windows: [],
    sparkline: { now_minute: 0, max: 0, series: [], all: { points: [] } },
    graph: { max: 0, cells: [] },
    config: { goalWords: 1000, goalAppClass: "obsidian", dailyNotePath: "", autoExport: false }
  }
}

function mergeStatus(raw) {
  var base = emptyStatus()
  if (!raw || typeof raw !== "object") return base
  for (var key in raw) base[key] = raw[key]
  if (!base.goal) base.goal = emptyStatus().goal
  if (!base.goals) base.goals = []
  if (!base.apps) base.apps = []
  if (!base.activities) base.activities = []
  if (!base.hypr_workspaces) base.hypr_workspaces = []
  if (!base.herdr_workspaces) base.herdr_workspaces = []
  if (!base.sites) base.sites = []
  if (!base.windows) base.windows = []
  if (!base.sparkline) base.sparkline = { now_minute: 0, max: 0, series: [] }
  if (!base.graph) base.graph = { max: 0, cells: [] }
  return base
}

function primaryGoal(status) {
  var list = goalList(status)
  return list.length ? list[0] : null
}

function barLabel(status, vertical) {
  if (!status) return "Words"
  if (status.state === "need_input_group") return vertical ? "Words" : ICON_WORDS + " setup"
  if (status.state === "error") return "Words"
  var today = Number(status.today_words)
  if (!isFinite(today)) {
    today = 0
    var rows = status.activities || []
    for (var i = 0; i < rows.length; i++) today += Number(rows[i].net_words || 0)
  }
  var live = Number(status.live_wpm || 0)
  if (vertical) return live > 0 ? String(Math.round(live)) : String(today)
  var main = live > 0 ? Math.round(live) + " · " + today : String(today)
  var goal = primaryGoal(status)
  var goalBit = ""
  if (goal && Number(goal.target || 0) > 0)
    goalBit = "  " + ICON_GOAL + " " + Number(goal.net_words || 0) + "/" + Number(goal.target)
  return ICON_WORDS + " " + main + goalBit
}

function tooltip(status) {
  if (!status) return "Words"
  if (status.state === "need_input_group")
    return "Cannot read the keyboard. Add your user to the input group, then log out."
  if (status.message && status.state !== "running") return String(status.message)
  var parts = []
  parts.push(Number(status.today_words || 0) + " today")
  var goal = status.goal || {}
  if (Number(goal.target || 0) > 0)
    parts.push((goal.label || "goal") + " " + Number(goal.net_words || 0) + "/" + Number(goal.target || 0))
  parts.push("Burst " + Math.round(Number(status.last_burst_wpm || 0)) + " WPM")
  return parts.join(" · ")
}

function graphColumns(cells) {
  var cols = []
  var col = [null, null, null, null, null, null, null]
  var started = false
  for (var i = 0; i < (cells || []).length; i++) {
    var cell = cells[i]
    var row = (Number(cell.weekday) + 1) % 7
    col[row] = cell
    started = true
    if (row === 6) {
      cols.push(col)
      col = [null, null, null, null, null, null, null]
      started = false
    }
  }
  if (started) cols.push(col)
  return cols
}

function levelFor(words, maxWords) {
  var n = Number(words || 0)
  if (n <= 0) return 0
  var max = Math.max(Number(maxWords || 0), 1)
  var t = n / max
  if (t < 0.15) return 1
  if (t < 0.35) return 2
  if (t < 0.65) return 3
  return 4
}

function windowsForApp(windows, appClass) {
  var out = []
  for (var i = 0; i < (windows || []).length; i++) {
    if (windows[i].app_class === appClass) out.push(windows[i])
  }
  return out
}

// btop's 5×5 table: left sample level × right sample level, 0–4.
var BRAILLE_5X5 = [
  ["⠀", "⢀", "⢠", "⢰", "⢸"],
  ["⡀", "⣀", "⣠", "⣰", "⣸"],
  ["⡄", "⣄", "⣤", "⣴", "⣼"],
  ["⡆", "⣆", "⣦", "⣶", "⣾"],
  ["⡇", "⣇", "⣧", "⣷", "⣿"]
]

function formatMinute(minute) {
  var m = Math.max(0, Math.floor(Number(minute) || 0))
  var hh = Math.floor(m / 60)
  var mm = m % 60
  return (hh < 10 ? "0" : "") + hh + ":" + (mm < 10 ? "0" : "") + mm
}

function activeWindowPoints(points) {
  var vals = points || []
  var start = 0
  while (start < vals.length && !(Number(vals[start]) > 0)) start++
  if (start >= vals.length)
    return { points: vals, start: 0 }
  start = Math.max(0, start - 2)
  return { points: vals.slice(start), start: start }
}

function downsampleMax(points, n) {
  n = Math.floor(Number(n) || 0)
  if (n <= 0) return []
  var values = []
  var i
  for (i = 0; i < (points || []).length; i++)
    values.push(Math.max(0, Number(points[i]) || 0))
  if (!values.length) {
    var zeros = []
    for (i = 0; i < n; i++) zeros.push(0)
    return zeros
  }
  if (values.length >= n) {
    var out = []
    for (i = 0; i < n; i++) {
      var start = Math.floor(i * values.length / n)
      var end = Math.max(start + 1, Math.floor((i + 1) * values.length / n))
      var m = 0
      for (var k = start; k < end && k < values.length; k++)
        if (values[k] > m) m = values[k]
      out.push(m)
    }
    return out
  }
  var padded = []
  for (i = 0; i < n - values.length; i++) padded.push(0)
  return padded.concat(values)
}

function brailleLevel(value, lo, hi) {
  if (value <= lo) return 0
  if (value >= hi) return 4
  var span = hi - lo
  if (span <= 0) return 4
  return Math.round((value - lo) / span * 4)
}

function brailleGraph(points, cols, rows, peak) {
  cols = Math.max(1, Math.floor(Number(cols) || 1))
  rows = Math.max(1, Math.floor(Number(rows) || 1))
  var windowed = activeWindowPoints(points)
  var samples = downsampleMax(windowed.points, cols * 2)
  var maxv = Number(peak)
  if (!isFinite(maxv) || maxv <= 0) {
    maxv = 0
    for (var s = 0; s < samples.length; s++)
      if (samples[s] > maxv) maxv = samples[s]
  }
  if (maxv < 0.01) maxv = 0.01
  var norm = []
  for (s = 0; s < samples.length; s++)
    norm.push(Math.min(1, samples[s] / maxv))
  var lines = []
  for (var row = 0; row < rows; row++) {
    var lo = (rows - 1 - row) / rows
    var hi = (rows - row) / rows
    var chars = ""
    for (var col = 0; col < cols; col++) {
      var left = brailleLevel(norm[col * 2], lo, hi)
      var right = brailleLevel(norm[col * 2 + 1], lo, hi)
      chars += BRAILLE_5X5[left][right]
    }
    lines.push(chars)
  }
  return lines
}

function focusedSeries(sparkline) {
  var series = (sparkline && sparkline.series) ? sparkline.series : []
  for (var i = 0; i < series.length; i++) {
    if (series[i] && series[i].focused === true) return series[i]
  }
  return series.length ? series[0] : null
}

function combinedSeries(sparkline) {
  if (sparkline && sparkline.all && sparkline.all.points)
    return sparkline.all
  var series = (sparkline && sparkline.series) ? sparkline.series : []
  if (!series.length) return { app_class: "", points: [] }
  var length = 0
  var i
  for (i = 0; i < series.length; i++)
    if (series[i].points && series[i].points.length > length)
      length = series[i].points.length
  var points = []
  for (i = 0; i < length; i++) {
    var sum = 0
    for (var s = 0; s < series.length; s++)
      sum += Number((series[s].points && series[s].points[i]) || 0)
    points.push(sum)
  }
  return { app_class: "", points: points }
}

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
  if (status && status.goals && status.goals.length) return status.goals
  if (status && status.goal) return [status.goal]
  return []
}

function emptyStatus() {
  return {
    state: "starting",
    message: "Starting…",
    paused: false,
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

function barLabel(status, vertical) {
  if (!status) return "WPM"
  if (status.state === "need_input_group") return vertical ? "WPM" : "WPM setup"
  if (status.state === "error") return "WPM"
  var goal = status.goal || {}
  var net = Number(goal.net_words || 0)
  var target = Number(goal.target || 0)
  var live = Number(status.live_wpm || 0)
  if (vertical) return live > 0 ? String(Math.round(live)) : String(net)
  if (live > 0) return Math.round(live) + " · " + net + "/" + target
  return net + "/" + target
}

function tooltip(status) {
  if (!status) return "WPM"
  if (status.state === "need_input_group")
    return "Cannot read the keyboard. Add your user to the input group, then log out."
  if (status.message && status.state !== "running") return String(status.message)
  var goal = status.goal || {}
  var parts = []
  parts.push("Goal " + (goal.label || goal.match || goal.app_class || "obsidian") + " " + Number(goal.net_words || 0) + "/" + Number(goal.target || 0))
  parts.push("Burst " + Math.round(Number(status.last_burst_wpm || 0)) + " WPM")
  parts.push("Session " + Math.round(Number(status.session_wpm || 0)) + " WPM")
  if (status.active_activity) parts.push(status.active_activity)
  else if (status.active_class) parts.push(status.active_class)
  if (status.active_hypr_workspace) parts.push("ws " + status.active_hypr_workspace)
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

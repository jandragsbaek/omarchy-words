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
    goal: { app_class: "obsidian", target: 1000, net_words: 0, inserted_words: 0, deleted_words: 0, percent: 0 },
    apps: [],
    windows: [],
    graph: { max: 0, cells: [] },
    config: { goalWords: 1000, goalAppClass: "obsidian", dailyNotePath: "", autoExport: false }
  }
}

function mergeStatus(raw) {
  var base = emptyStatus()
  if (!raw || typeof raw !== "object") return base
  for (var key in raw) base[key] = raw[key]
  if (!base.goal) base.goal = emptyStatus().goal
  if (!base.apps) base.apps = []
  if (!base.windows) base.windows = []
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
  parts.push("Goal " + (goal.app_class || "obsidian") + " " + Number(goal.net_words || 0) + "/" + Number(goal.target || 0))
  parts.push("Burst " + Math.round(Number(status.last_burst_wpm || 0)) + " WPM")
  parts.push("Session " + Math.round(Number(status.session_wpm || 0)) + " WPM")
  if (status.active_class) parts.push(status.active_class)
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

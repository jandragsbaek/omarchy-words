import QtQuick
import Quickshell
import Quickshell.Io
import "Model.js" as Model

Item {
  id: root

  property var shell: null
  property var manifest: null
  property var settings: ({})

  property var snapshot: Model.emptyStatus()
  property string lastError: ""
  property bool expectedStop: false
  property int restartAttempt: 0

  readonly property string moduleName: "jandragsbaek.words"
  readonly property string runtimeDir: Quickshell.env("XDG_RUNTIME_DIR") || "/tmp"
  readonly property string statusPath: runtimeDir + "/omawpm/status.json"

  function localPath(url) {
    var text = String(url || "")
    if (text.indexOf("file://") === 0) text = text.substring(7)
    return decodeURIComponent(text)
  }

  readonly property string cliPath: localPath(Qt.resolvedUrl("bin/omawpm"))

  function applyText(text) {
    snapshot = Model.mergeStatus(Model.parseStatus(text))
  }

  function syncConfig() {
    var goalWords = settings && settings.goalWords !== undefined ? settings.goalWords : 1000
    var goalMatch = settings && settings.goalMatch ? settings.goalMatch : (settings && settings.goalAppClass ? settings.goalAppClass : "obsidian")
    var goalApp = settings && settings.goalAppClass ? settings.goalAppClass : goalMatch
    var goals = settings && settings.goals !== undefined && settings.goals !== null ? settings.goals : ""
    if (typeof goals !== "string") goals = JSON.stringify(goals)
    var note = settings && settings.dailyNotePath ? settings.dailyNotePath : ""
    var autoExport = settings && settings.autoExport === true
    configWriter.command = ["python3", cliPath, "config", "goalWords", String(goalWords)]
    configWriter.running = false
    configBundle.goalWords = String(goalWords)
    configBundle.goalMatch = String(goalMatch)
    configBundle.goalAppClass = String(goalApp)
    configBundle.goals = String(goals)
    configBundle.dailyNotePath = String(note)
    configBundle.autoExport = autoExport ? "true" : "false"
    configBundle.start()
  }

  function pause(paused) {
    pauseProc.command = ["python3", cliPath, paused ? "pause" : "resume"]
    pauseProc.running = true
  }

  function exportNote() {
    exportProc.command = ["python3", cliPath, "export"]
    exportProc.running = true
  }

  function explore() {
    exploreProc.command = ["python3", cliPath, "explore"]
    exploreProc.running = true
  }

  function report() {
    reportProc.command = ["python3", cliPath, "report"]
    reportProc.running = true
  }

  function setGoals(json) {
    goalsWriter.command = ["python3", cliPath, "config", "goals", String(json || "[]")]
    goalsWriter.running = true
  }

  onSettingsChanged: Qt.callLater(syncConfig)

  QtObject {
    id: configBundle
    property string goalWords: "1000"
    property string goalMatch: "obsidian"
    property string goalAppClass: "obsidian"
    property string goals: ""
    property string dailyNotePath: ""
    property string autoExport: "false"
    property int step: 0

    function start() {
      step = 0
      next()
    }

    function next() {
      var keys = ["goalWords", "goalMatch", "goalAppClass", "goals", "dailyNotePath", "autoExport"]
      var values = [goalWords, goalMatch, goalAppClass, goals, dailyNotePath, autoExport]
      if (step >= keys.length) return
      if (keys[step] === "goals" && (!goals || goals === "" || goals === "[]")) {
        step += 1
        next()
        return
      }
      configWriter.command = ["python3", root.cliPath, "config", keys[step], values[step]]
      configWriter.running = true
    }
  }

  Process {
    id: configWriter
    running: false
    onExited: {
      configBundle.step += 1
      if (configBundle.step < 6) configBundle.next()
    }
  }

  Process {
    id: pauseProc
    running: false
  }

  Process {
    id: exportProc
    running: false
  }

  Process {
    id: exploreProc
    running: false
  }

  Process {
    id: reportProc
    running: false
  }

  Process {
    id: goalsWriter
    running: false
  }

  FileView {
    id: statusFile
    path: root.statusPath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.applyText(text())
  }

  Timer {
    interval: 800
    running: true
    repeat: true
    onTriggered: statusFile.reload()
  }

  Process {
    id: backend
    command: ["python3", root.cliPath, "daemon"]
    running: false

    stderr: SplitParser {
      onRead: function(line) {
        var text = String(line || "").trim()
        if (text) root.lastError = text
      }
    }

    onExited: function(code) {
      if (root.expectedStop) return
      root.restartAttempt = Math.min(root.restartAttempt + 1, 6)
      restartTimer.interval = Math.min(15000, 800 * Math.pow(2, root.restartAttempt - 1))
      restartTimer.restart()
    }
  }

  Timer {
    id: restartTimer
    repeat: false
    onTriggered: if (!root.expectedStop && !backend.running) backend.running = true
  }

  Component.onCompleted: {
    backend.running = true
    Qt.callLater(syncConfig)
  }

  Component.onDestruction: {
    expectedStop = true
    backend.running = false
  }
}

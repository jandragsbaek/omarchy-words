import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "jandragsbaek.wpm"
  ipcTarget: "jandragsbaek.wpm"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  property var service: null
  readonly property var barIdentity: hostWidget || root

  property bool yearOpen: false
  property string soloActivity: ""
  readonly property int listLimit: 10

  readonly property var status: service && service.snapshot ? service.snapshot : Model.emptyStatus()
  readonly property var activities: status.activities || []
  readonly property var apps: status.apps || []
  readonly property var activityRows: {
    if (activities && activities.length)
      return activities
    var out = []
    var list = apps || []
    for (var i = 0; i < list.length; i++) {
      out.push({
        name: list[i].app_class,
        app_class: list[i].app_class,
        inserted_chars: list[i].inserted_chars,
        deleted_chars: list[i].deleted_chars,
        inserted_words: list[i].inserted_words,
        deleted_words: list[i].deleted_words,
        net_words: list[i].net_words
      })
    }
    return out
  }
  readonly property var visibleRows: Model.visibleActivities(
    activityRows,
    status.active_activity || "",
    soloActivity,
    listLimit
  )
  readonly property int overflowCount: Math.max(0, activityRows.length - listLimit)
  readonly property var goals: Model.goalList(status)
  readonly property var sparkline: status.sparkline || { now_minute: 0, max: 0, series: [] }
  readonly property var graph: status.graph || { max: 0, cells: [] }
  readonly property var columns: Model.graphColumns(graph.cells || [])
  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property color contentMuted: Color.muted
  readonly property color contentAccent: Color.accent
  readonly property color contentUrgent: (bar && bar.urgent) ? bar.urgent : Color.urgent
  readonly property color hoverFill: bar ? Style.hoverFillFor(contentForeground, Color.accent) : Style.hoverFill
  readonly property color selectedFill: bar ? Style.selectedFillFor(contentForeground, Color.accent) : Style.selectedFill
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color plusColor: contentAccent
  readonly property color minusColor: contentUrgent

  readonly property int cell: Style.space(11)
  readonly property int cellGap: Style.space(3)
  readonly property int graphWidth: columns.length * (cell + cellGap)

  readonly property bool setupMode: status.state === "need_input_group"
  readonly property bool pausedMode: status.state === "paused"
  readonly property int liveWpm: Math.round(Number(status.live_wpm || 0))
  readonly property int burstWpm: Math.round(Number(status.last_burst_wpm || 0))
  readonly property int sessionWpm: Math.round(Number(status.session_wpm || 0))
  readonly property int todayWords: {
    var n = 0
    var rows = activityRows
    for (var i = 0; i < rows.length; i++) n += Number(rows[i].net_words || 0)
    return n
  }
  readonly property int heroValue: {
    if (setupMode) return 0
    if (liveWpm > 0) return liveWpm
    if (todayWords > 0) return todayWords
    return sessionWpm
  }
  readonly property string heroUnit: {
    if (setupMode) return "setup"
    if (liveWpm > 0) return "WPM"
    if (todayWords > 0) return "today"
    return "WPM"
  }
  readonly property bool showBurst: burstWpm > 0 && burstWpm !== liveWpm
  readonly property bool showSession: sessionWpm > 0 && (liveWpm > 0 ? sessionWpm !== liveWpm : true)
  readonly property bool hasTyping: activityRows.length > 0 || Number(sparkline.max || 0) > 0
  readonly property var combinedSpark: Model.combinedSeries(sparkline)
  readonly property var activeSpark: {
    if (soloActivity) {
      var locked = Model.seriesByName(sparkline, soloActivity)
      if (locked) return locked
    }
    return combinedSpark
  }
  readonly property var sparkWindow: Model.activeWindowPoints(activeSpark && activeSpark.points ? activeSpark.points : [])
  readonly property real sparkPeak: {
    var local = Model.seriesPeak(sparkWindow.points)
    return local > 0 ? local : Number(sparkline.max || 0)
  }
  readonly property var sparkLines: Model.brailleGraph(
    sparkWindow.points,
    sparkCols,
    sparkRowCount,
    sparkPeak
  )
  readonly property int sparkRowCount: 3
  property int sparkCols: 48

  function open() {
    root.controller.show()
    Qt.callLater(function() {
      if (root.opened) setCenterHoverRevealSuppressed(true)
    })
  }

  function close() {
    setCenterHoverRevealSuppressed(false)
    root.yearOpen = false
    root.soloActivity = ""
    root.controller.hide()
  }

  function toggleSolo(name) {
    name = String(name || "")
    root.soloActivity = root.soloActivity === name ? "" : name
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }

  function setCenterHoverRevealSuppressed(value) {
    if (root.bar && "centerHoverRevealSuppressed" in root.bar)
      root.bar.centerHoverRevealSuppressed = value
  }

  function cellFill(level) {
    if (level <= 0) return Util.alpha(contentForeground, 0.08)
    return Util.alpha(contentAccent, Math.min(0.95, 0.22 + level * 0.18))
  }

  FontMetrics {
    id: wordMetrics
    font.family: contentFontFamily
    font.pixelSize: Style.font.heading
    font.bold: true
  }

  FontMetrics {
    id: toolMetrics
    font.family: contentFontFamily
    font.pixelSize: Style.font.bodySmall
  }

  readonly property var statsDigits: Model.statsDigits(visibleRows)
  readonly property real wordDigitW: Math.max(8, wordMetrics.averageCharacterWidth)
  readonly property int wordColW: Math.ceil(wordDigitW * Number(statsDigits.words || 1)) + Style.space(2)
  readonly property int aiWords: {
    var n = 0
    var rows = activityRows
    for (var i = 0; i < rows.length; i++) {
      if (Model.aiTool(Model.rowName(rows[i])))
        n += Number(rows[i].net_words || 0)
    }
    return n
  }
  readonly property int toolColW: {
    var m = 0
    var rows = visibleRows
    for (var i = 0; i < rows.length; i++) {
      var t = Model.rowTool(Model.rowName(rows[i]))
      if (t.length > m) m = t.length
    }
    if (m <= 0) return 0
    return Math.ceil(Math.max(6, toolMetrics.averageCharacterWidth) * m)
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(root.yearOpen ? Style.space(820) : Style.space(480))
    contentHeight: panel.fittedContentHeight(body.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onActivateRequested: root.yearOpen = !root.yearOpen
      onTextKey: function(t) {
        if (t === "y" || t === "Y") root.yearOpen = !root.yearOpen
        else if (t === "e" || t === "E") { if (root.service) root.service.exportNote() }
        else if (t === "o" || t === "O") { if (root.service) root.service.explore() }
        else if (t === "r" || t === "R") { if (root.service) root.service.report() }
        else if (t === "p" || t === "P") {
          if (root.service) root.service.pause(root.status.state !== "paused")
        }
      }

      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: body.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
          id: body
          width: scroll.width
          spacing: Style.space(12)

          // Hero: big rate on the left, only the meta that isn't already in the number.
          Item {
            width: parent.width
            height: Math.max(heroLeft.height, heroRight.height)

            Row {
              id: heroLeft
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(8)

              Text {
                id: heroNum
                text: root.setupMode ? "—" : String(root.heroValue)
                color: contentForeground
                font.family: contentFontFamily
                font.pixelSize: 48
                font.bold: true
              }

              Text {
                text: root.setupMode ? "setup" : root.heroUnit
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.display
                font.bold: false
                anchors.top: heroNum.top
                anchors.topMargin: Style.space(10)
              }
            }

            Column {
              id: heroRight
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(2)
              visible: root.setupMode || root.pausedMode || root.showBurst || root.showSession || (root.todayWords > 0 && root.liveWpm > 0) || root.aiWords > 0

              Text {
                visible: root.setupMode
                text: "input group"
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
                horizontalAlignment: Text.AlignRight
              }

              Text {
                visible: root.pausedMode && !root.setupMode
                text: "paused"
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
                horizontalAlignment: Text.AlignRight
              }

              Text {
                visible: root.showBurst
                text: "burst " + root.burstWpm
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
                horizontalAlignment: Text.AlignRight
              }

              Text {
                visible: root.showSession
                text: "session " + root.sessionWpm
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
                horizontalAlignment: Text.AlignRight
              }

              Text {
                visible: root.todayWords > 0 && root.liveWpm > 0 && !root.setupMode
                text: root.todayWords + " today"
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
                horizontalAlignment: Text.AlignRight
              }

              Text {
                visible: root.aiWords > 0 && !root.setupMode
                text: root.aiWords + " AI"
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
                horizontalAlignment: Text.AlignRight
              }
            }
          }

          Text {
            visible: root.setupMode
            width: parent.width
            wrapMode: Text.WordWrap
            text: "sudo usermod -aG input $USER"
            color: contentMuted
            font.family: contentFontFamily
            font.pixelSize: Style.font.bodySmall
          }

          // Goals with progress get a bar. Empty goals stay out of the way while you're writing elsewhere.
          Column {
            width: parent.width
            spacing: Style.space(6)
            visible: {
              if (!(goals && goals.length) || Number((goals[0] && goals[0].target) || 0) <= 0)
                return false
              if (!root.hasTyping) return true
              for (var i = 0; i < goals.length; i++)
                if (Number(goals[i].net_words || 0) > 0) return true
              return false
            }

            Repeater {
              model: goals

              Column {
                required property var modelData
                required property int index
                width: body.width
                spacing: Style.space(3)
                visible: Number(modelData.net_words || 0) > 0 || !root.hasTyping
                readonly property bool emptyGoal: Number(modelData.net_words || 0) <= 0

                Item {
                  width: parent.width
                  height: goalName.implicitHeight

                  Text {
                    id: goalName
                    anchors.left: parent.left
                    anchors.right: goalCount.left
                    anchors.rightMargin: Style.space(10)
                    elide: Text.ElideRight
                    text: Model.displayName(String(modelData.label || modelData.match || ""))
                    color: emptyGoal ? contentMuted : contentForeground
                    font.family: contentFontFamily
                    font.pixelSize: Style.font.body
                    font.bold: !emptyGoal
                  }

                  Text {
                    id: goalCount
                    anchors.right: parent.right
                    text: Number(modelData.net_words || 0) + " / " + Number(modelData.target || 0)
                    color: Number(modelData.percent || 0) >= 100 ? plusColor : (emptyGoal ? contentMuted : contentForeground)
                    font.family: contentFontFamily
                    font.pixelSize: Style.font.body
                  }
                }

                Rectangle {
                  width: parent.width
                  height: 3
                  radius: 1
                  visible: !emptyGoal
                  color: Util.alpha(contentForeground, 0.08)

                  Rectangle {
                    width: parent.width * Math.min(1, Number(modelData.percent || 0) / 100)
                    height: parent.height
                    radius: parent.radius
                    color: contentAccent
                  }
                }
              }
            }
          }

          // Today spark — focused series only. Legend is the list below.
          Column {
            width: parent.width
            spacing: Style.space(4)
            visible: root.hasTyping

            Item {
              width: parent.width
              height: sparkCap.implicitHeight

              Text {
                id: sparkCap
                width: parent.width
                elide: Text.ElideRight
                text: {
                  var range = Model.formatMinute(sparkWindow.start) + "–" + Model.formatMinute(sparkline.now_minute)
                  return root.soloActivity ? range + "  solo" : range
                }
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
              }
            }

            FontMetrics {
              id: sparkMetrics
              font.family: contentFontFamily
              font.pixelSize: Style.font.bodySmall
            }

            Row {
              width: parent.width
              spacing: Style.space(6)

              Item {
                width: Style.space(32)
                height: sparkBox.height

                Text {
                  anchors.top: parent.top
                  anchors.right: parent.right
                  text: Number(sparkPeak || 0) > 0 ? String(Math.round(Number(sparkPeak))) : "0"
                  color: contentMuted
                  font.family: contentFontFamily
                  font.pixelSize: Style.font.caption
                }

                Text {
                  anchors.bottom: parent.bottom
                  anchors.right: parent.right
                  text: "0"
                  color: contentMuted
                  font.family: contentFontFamily
                  font.pixelSize: Style.font.caption
                }
              }

              Rectangle {
                id: sparkBox
                width: parent.width - Style.space(32) - Style.space(6)
                implicitHeight: sparkInner.implicitHeight + Style.space(4)
                color: "transparent"
                border.width: 1
                border.color: Style.normalBorderFor(contentForeground, Color.accent)
                radius: 0

                Column {
                  id: sparkInner
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.leftMargin: Style.space(4)
                  anchors.rightMargin: Style.space(4)
                  spacing: 0

                  function refreshCols() {
                    var cw = sparkMetrics.averageCharacterWidth
                    root.sparkCols = Math.max(12, Math.floor(width / Math.max(6, cw)))
                  }
                  onWidthChanged: refreshCols()
                  Component.onCompleted: refreshCols()

                  Repeater {
                    model: sparkLines

                    Text {
                      required property string modelData
                      width: sparkInner.width
                      text: modelData
                      color: contentAccent
                      font.family: contentFontFamily
                      font.pixelSize: Style.font.bodySmall
                      font.letterSpacing: 0
                      renderType: Text.NativeRendering
                    }
                  }
                }
              }
            }
          }

          // One list: where the words went. No ACTIVITY / HERDR / WORKSPACES repeats.
          Column {
            width: parent.width
            spacing: Style.space(4)
            visible: root.hasTyping

            Repeater {
              model: visibleRows

              Item {
                required property var modelData
                width: body.width
                height: Math.max(actName.implicitHeight, wordNum.implicitHeight) + Style.space(8)
                readonly property string rowName: Model.rowName(modelData)
                readonly property bool selected: root.soloActivity !== "" && rowName === root.soloActivity

                Rectangle {
                  anchors.fill: parent
                  radius: Style.space(4)
                  color: {
                    if (selected && root.soloActivity)
                      return root.selectedFill
                    if (rowMouse.containsMouse)
                      return root.hoverFill
                    return "transparent"
                  }
                }

                Rectangle {
                  visible: selected
                  width: 2
                  height: parent.height - Style.space(4)
                  radius: 1
                  anchors.left: parent.left
                  anchors.verticalCenter: parent.verticalCenter
                  color: contentAccent
                }

                Text {
                  id: actName
                  anchors.left: parent.left
                  anchors.leftMargin: Style.space(8)
                  anchors.right: toolLabel.left
                  anchors.rightMargin: root.toolColW > 0 ? Style.space(8) : Style.space(10)
                  anchors.verticalCenter: parent.verticalCenter
                  elide: Text.ElideRight
                  text: Model.displayName(rowName)
                  color: contentForeground
                  font.family: contentFontFamily
                  font.pixelSize: Style.font.body
                }

                Text {
                  id: toolLabel
                  width: root.toolColW
                  visible: root.toolColW > 0
                  anchors.right: parenRow.left
                  anchors.rightMargin: root.toolColW > 0 ? Style.space(8) : 0
                  anchors.verticalCenter: parent.verticalCenter
                  text: Model.rowTool(rowName)
                  color: contentMuted
                  font.family: contentFontFamily
                  font.pixelSize: Style.font.bodySmall
                  horizontalAlignment: Text.AlignRight
                }

                Row {
                  id: parenRow
                  anchors.right: wordNum.left
                  anchors.rightMargin: Style.space(10)
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: 0

                  Text {
                    text: "("
                    color: contentMuted
                    font.family: contentFontFamily
                    font.pixelSize: Style.font.bodySmall
                  }

                  Text {
                    text: "+" + Number(modelData.inserted_chars || 0)
                    color: plusColor
                    font.family: contentFontFamily
                    font.pixelSize: Style.font.bodySmall
                  }

                  Text {
                    visible: Number(modelData.deleted_chars || 0) > 0
                    text: " −" + Number(modelData.deleted_chars || 0)
                    color: minusColor
                    font.family: contentFontFamily
                    font.pixelSize: Style.font.bodySmall
                  }

                  Text {
                    text: ")"
                    color: contentMuted
                    font.family: contentFontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                }

                Text {
                  id: wordNum
                  width: root.wordColW
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  horizontalAlignment: Text.AlignRight
                  text: String(Number(modelData.net_words || 0))
                  color: contentForeground
                  font.family: contentFontFamily
                  font.pixelSize: Style.font.heading
                  font.bold: true
                }

                MouseArea {
                  id: rowMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.toggleSolo(rowName)
                }
              }
            }

            Text {
              visible: overflowCount > 0
              text: overflowCount + " more"
              color: contentMuted
              font.family: contentFontFamily
              font.pixelSize: Style.font.bodySmall

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: if (root.service) root.service.explore()
              }
            }
          }

          Text {
            visible: !root.hasTyping && !root.setupMode
            text: "No typing yet today."
            color: contentMuted
            font.family: contentFontFamily
            font.pixelSize: Style.font.body
          }

          Column {
            width: parent.width
            spacing: Style.space(8)
            visible: root.yearOpen

            Text {
              text: "YEAR"
              color: contentMuted
              font.family: contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.letterSpacing: 1.2
            }

            Flickable {
              width: parent.width
              height: 7 * (root.cell + root.cellGap)
              contentWidth: Math.max(width, root.graphWidth)
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              interactive: contentWidth > width

              Row {
                spacing: root.cellGap

                Repeater {
                  model: root.columns

                  Column {
                    id: weekCol
                    required property var modelData
                    spacing: root.cellGap

                    Repeater {
                      model: 7

                      Rectangle {
                        required property int index
                        property var cell: weekCol.modelData ? weekCol.modelData[index] : null
                        width: root.cell
                        height: root.cell
                        radius: Style.space(2)
                        color: root.cellFill(cell ? Model.levelFor(cell.net_words, graph.max) : 0)
                        opacity: cell ? 1 : 0.35

                        MouseArea {
                          anchors.fill: parent
                          hoverEnabled: true
                          enabled: !!cell

                          PanelToolTip {
                            visible: parent.containsMouse && !!cell
                            text: cell ? (cell.day + " · " + cell.net_words + " words") : ""
                            fontFamily: contentFontFamily
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }

          Item {
            width: parent.width
            height: footerLeft.height

            Row {
              id: footerLeft
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(14)

              Text {
                text: "E export"
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: if (root.service) root.service.exportNote()
                }
              }

              Text {
                text: status.state === "paused" ? "P resume" : "P pause"
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: if (root.service) root.service.pause(root.status.state !== "paused")
                }
              }

              Text {
                text: "O all"
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: if (root.service) root.service.explore()
                }
              }

              Text {
                text: "R report"
                color: contentMuted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: if (root.service) root.service.report()
                }
              }
            }

            Text {
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: root.yearOpen ? "Y hide" : "Y year"
              color: contentMuted
              font.family: contentFontFamily
              font.pixelSize: Style.font.bodySmall

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.yearOpen = !root.yearOpen
              }
            }
          }
        }
      }
    }
  }
}

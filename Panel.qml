import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "jan.wpm"
  ipcTarget: "jan.wpm"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  property var service: null
  readonly property var barIdentity: hostWidget || root

  property bool yearOpen: false
  property string expandedApp: ""

  readonly property var status: service && service.snapshot ? service.snapshot : Model.emptyStatus()
  readonly property var goal: status.goal || {}
  readonly property var apps: status.apps || []
  readonly property var windows: status.windows || []
  readonly property var graph: status.graph || { max: 0, cells: [] }
  readonly property var columns: Model.graphColumns(graph.cells || [])
  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color plusColor: Color.accent
  readonly property color minusColor: Color.urgent

  readonly property int cell: Style.space(11)
  readonly property int cellGap: Style.space(3)
  readonly property int graphWidth: columns.length * (cell + cellGap)

  function open() {
    root.controller.show()
    Qt.callLater(function() {
      if (root.opened) setCenterHoverRevealSuppressed(true)
    })
  }

  function close() {
    setCenterHoverRevealSuppressed(false)
    root.yearOpen = false
    root.controller.hide()
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
    if (level <= 0) return Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.08)
    var a = 0.22 + level * 0.18
    return Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, Math.min(0.95, a))
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(root.yearOpen ? Style.space(820) : Style.space(560))
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
          spacing: Style.space(10)

          // Hero: live WPM + goal
          Column {
            width: parent.width
            spacing: Style.space(4)

            Text {
              anchors.horizontalCenter: parent.horizontalCenter
              text: status.state === "need_input_group" ? "Needs input group" : (status.state === "paused" ? "Paused" : (Number(status.live_wpm) > 0 ? Math.round(status.live_wpm) + " WPM" : Math.round(Number(status.session_wpm || 0)) + " WPM avg"))
              color: contentForeground
              font.family: contentFontFamily
              font.pixelSize: 44
              font.bold: true
            }

            Text {
              anchors.horizontalCenter: parent.horizontalCenter
              text: {
                if (status.state === "need_input_group")
                  return "sudo usermod -aG input $USER"
                return "burst " + Math.round(Number(status.last_burst_wpm || 0)) + " · session " + Math.round(Number(status.session_wpm || 0))
              }
              color: Color.muted
              font.family: contentFontFamily
              font.pixelSize: Style.font.body
            }
          }

          // Goal
          Column {
            width: parent.width
            spacing: Style.space(6)

            Row {
              width: parent.width
              spacing: Style.space(8)

              Text {
                text: (goal.app_class || "obsidian") + "  " + Number(goal.net_words || 0) + " / " + Number(goal.target || 0)
                color: contentForeground
                font.family: contentFontFamily
                font.pixelSize: Style.font.title
                font.bold: true
              }

              Text {
                text: Model.gitDiff(goal.inserted_words, goal.deleted_words)
                color: Color.muted
                font.family: contentFontFamily
                font.pixelSize: Style.font.body
                anchors.verticalCenter: parent.verticalCenter
              }

              Item { width: 1; height: 1 }

              Text {
                text: Number(goal.percent || 0) + "%"
                color: Number(goal.percent || 0) >= 100 ? plusColor : contentForeground
                font.family: contentFontFamily
                font.pixelSize: Style.font.body
                anchors.verticalCenter: parent.verticalCenter
              }
            }

            Rectangle {
              width: parent.width
              height: Style.space(6)
              radius: height / 2
              color: Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.08)

              Rectangle {
                width: parent.width * Math.min(1, Number(goal.percent || 0) / 100)
                height: parent.height
                radius: parent.radius
                color: Color.accent
              }
            }
          }

          // Per-app git diffs
          Column {
            width: parent.width
            spacing: Style.space(2)

            Text {
              text: "APPS"
              color: Color.muted
              font.family: contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.letterSpacing: 1.2
            }

            Repeater {
              model: apps

              Column {
                required property var modelData
                width: body.width
                spacing: Style.space(2)

                Rectangle {
                  width: parent.width
                  height: appRow.implicitHeight + Style.space(8)
                  radius: Style.space(6)
                  color: appMouse.containsMouse
                    ? Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.06)
                    : "transparent"

                  Row {
                    id: appRow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: Style.space(6)
                    anchors.rightMargin: Style.space(6)
                    spacing: Style.space(10)

                    Text {
                      width: Math.max(Style.space(140), parent.width * 0.38)
                      elide: Text.ElideRight
                      text: String(modelData.app_class || "")
                      color: contentForeground
                      font.family: contentFontFamily
                      font.pixelSize: Style.font.body
                    }

                    Text {
                      text: "+" + Number(modelData.inserted_words || 0)
                      color: plusColor
                      font.family: contentFontFamily
                      font.pixelSize: Style.font.body
                    }

                    Text {
                      text: "−" + Number(modelData.deleted_words || 0)
                      color: minusColor
                      font.family: contentFontFamily
                      font.pixelSize: Style.font.body
                    }

                    Item { width: 1; height: 1 }

                    Text {
                      text: Number(modelData.net_words || 0) + " words"
                      color: Color.muted
                      font.family: contentFontFamily
                      font.pixelSize: Style.font.body
                    }
                  }

                  MouseArea {
                    id: appMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                      var klass = String(modelData.app_class || "")
                      root.expandedApp = root.expandedApp === klass ? "" : klass
                    }
                  }
                }

                Repeater {
                  model: root.expandedApp === String(modelData.app_class || "")
                    ? Model.windowsForApp(root.windows, modelData.app_class)
                    : []

                  Row {
                    required property var modelData
                    width: body.width
                    leftPadding: Style.space(18)
                    spacing: Style.space(8)

                    Text {
                      width: Math.max(Style.space(180), parent.width * 0.5)
                      elide: Text.ElideRight
                      text: String(modelData.title || "(untitled)")
                      color: Color.muted
                      font.family: contentFontFamily
                      font.pixelSize: Style.font.bodySmall
                    }

                    Text {
                      text: "+" + Number(modelData.inserted_words || 0)
                      color: plusColor
                      font.family: contentFontFamily
                      font.pixelSize: Style.font.bodySmall
                    }

                    Text {
                      text: "−" + Number(modelData.deleted_words || 0)
                      color: minusColor
                      font.family: contentFontFamily
                      font.pixelSize: Style.font.bodySmall
                    }
                  }
                }
              }
            }

            Text {
              visible: apps.length === 0
              text: "No typing counted yet today."
              color: Color.muted
              font.family: contentFontFamily
              font.pixelSize: Style.font.body
            }
          }

          // Contribution graph
          Column {
            width: parent.width
            spacing: Style.space(6)
            visible: root.yearOpen || columns.length > 0

            Row {
              width: parent.width
              spacing: Style.space(8)

              Text {
                text: "YEAR"
                color: Color.muted
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
                font.letterSpacing: 1.2
                anchors.verticalCenter: parent.verticalCenter
              }

              Item { width: 1; height: 1 }

              Text {
                text: root.yearOpen ? "collapse" : "expand"
                color: Color.accent
                font.family: contentFontFamily
                font.pixelSize: Style.font.bodySmall
                anchors.verticalCenter: parent.verticalCenter

                MouseArea {
                  anchors.fill: parent
                  anchors.margins: -4
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.yearOpen = !root.yearOpen
                }
              }
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

          Row {
            spacing: Style.space(16)

            Text {
              text: "E export"
              color: Color.muted
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
              color: Color.muted
              font.family: contentFontFamily
              font.pixelSize: Style.font.bodySmall

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: if (root.service) root.service.pause(root.status.state !== "paused")
              }
            }

            Text {
              text: "Y year"
              color: Color.muted
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

import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

BarWidget {
  id: root
  moduleName: "jandragsbaek.words"

  readonly property var service: bar && bar.shell && bar.shell.serviceFor ? bar.shell.serviceFor(moduleName) : null
  readonly property var status: service && service.snapshot ? service.snapshot : Model.emptyStatus()
  readonly property string label: Model.barLabel(status, vertical)

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
    if ("service" in target) target.service = root.service
  }

  function togglePanel() {
    if (panelLoader.item && panelLoader.item.toggle) panelLoader.item.toggle()
  }

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() {
    if (panelLoader.item && panelLoader.item.open) panelLoader.item.open()
  }

  function close() {
    if (panelLoader.item && panelLoader.item.close) panelLoader.item.close()
  }

  property bool popoutSwitchClosing: false

  function closeForPopoutSwitch() {
    popoutSwitchClosing = true
    close()
    popoutTimer.restart()
  }

  Timer {
    id: popoutTimer
    interval: 120
    onTriggered: root.popoutSwitchClosing = false
  }

  function syncService() {
    if (service) service.settings = root.settings
  }

  onBarChanged: injectPanel()
  onSettingsChanged: {
    injectPanel()
    syncService()
  }
  onServiceChanged: {
    injectPanel()
    syncService()
  }

  Component.onCompleted: {
    injectPanel()
    syncService()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  IpcHandler {
    target: "jandragsbaek.words"
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.togglePanel() }
    function exportNote(): void { if (root.service) root.service.exportNote() }
    function explore(): void { if (root.service) root.service.explore() }
    function report(): void { if (root.service) root.service.report() }
    function pause(): void { if (root.service) root.service.pause(true) }
    function resume(): void { if (root.service) root.service.pause(false) }
  }

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.vertical ? "" : root.label
    labelVisible: !root.vertical
    hasVisualContent: true
    tooltipText: Model.tooltip(root.status)
    active: false
    useActiveColor: false
    horizontalMargin: 8.75
    verticalPadding: 8.75

    onPressed: function(b) {
      if (b === Qt.RightButton) {
        if (root.service) root.service.pause(!(root.status.paused === true && root.status.state === "paused"))
      } else if (b === Qt.MiddleButton) {
        if (root.service) root.service.exportNote()
      } else {
        root.togglePanel()
      }
    }

    Text {
      visible: root.vertical
      anchors.centerIn: parent
      rotation: 90
      text: root.label
      color: button.foreground
      font.family: button.fontFamily
      font.pixelSize: button.fontSize
    }
  }
}

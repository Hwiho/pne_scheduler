import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

// The one GUI for authoring a schedule: 설정 → 프로토콜 → 절차 → 검증 → 내보내기.
ApplicationWindow {
    id: appWindow
    visible: true
    width: 1440
    height: 940
    minimumWidth: 1100
    minimumHeight: 700
    color: Theme.bg
    title: "PNE 스케줄 워크스페이스 — " + workspace.title

    property var pendingConfirm: null
    property string pendingExport: ""

    function goToTab(index) { tabBar.currentIndex = index }

    function showNotice(title, body, kind) {
        noticeDialog.title = title
        noticeDialog.text = title
        noticeDialog.informativeText = body
        noticeDialog.open()
    }

    function confirm(title, body, action) {
        appWindow.pendingConfirm = action
        confirmDialog.title = title
        confirmDialog.text = title
        confirmDialog.informativeText = body
        confirmDialog.open()
    }

    function saveOrPrompt() {
        if (workspace.needsSavePath())
            saveDialog.open()
        else
            workspace.save()
    }

    function runExport(kind) {
        appWindow.pendingExport = kind
        if (kind === "draft_save")
            saveOrPrompt()
        else if (kind === "preview")
            folderDialog.open()
        else if (kind === "review_candidate")
            folderDialog.open()
        else if (kind === "template_patch")
            workspace.templatePatchHelp()
        else if (kind === "equipment_export")
            workspace.equipmentExport()
    }

    // ------------------------------------------------------------- header

    header: ToolBar {
        background: Rectangle { color: Theme.panel; border.color: Theme.line; border.width: 1 }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.pad
            anchors.rightMargin: Theme.pad
            spacing: 8

            Button { text: "새로 만들기"; onClicked: workspace.newProject() }
            Button { text: "열기"; onClicked: openDialog.open() }
            Button { text: "저장"; onClicked: appWindow.saveOrPrompt() }
            Button {
                text: "실행 취소"
                enabled: workspace.canUndo
                ToolTip.visible: hovered && workspace.canUndo
                ToolTip.text: workspace.undoLabel
                onClicked: workspace.undo()
            }
            Button {
                text: "다시 실행"
                enabled: workspace.canRedo
                ToolTip.visible: hovered && workspace.canRedo
                ToolTip.text: workspace.redoLabel
                onClicked: workspace.redo()
            }

            ToolSeparator {}

            ComboBox {
                Layout.preferredWidth: 150
                model: ["고급 도구…", "SCH 뷰어", "플로우 캔버스", "일괄 편집기", "중단 실험 재개"]
                onActivated: function (index) {
                    var names = ["", "viewer", "flow", "editor", "resume"]
                    if (index > 0)
                        workspace.openLegacyTool(names[index])
                    currentIndex = 0
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: workspace.summaryHeadline
                color: Theme.muted
                font.pixelSize: 12
                elide: Text.ElideRight
                Layout.maximumWidth: 520
            }

            Rectangle {
                radius: Theme.radius
                color: Theme.accentSoft
                border.color: Theme.accent
                implicitWidth: stageText.implicitWidth + 20
                implicitHeight: 28
                Text {
                    id: stageText
                    anchors.centerIn: parent
                    text: "진행 상태: " + workspace.stageLabel
                    color: Theme.accent
                    font.pixelSize: 12
                    font.bold: true
                }
            }
        }
    }

    // --------------------------------------------------------------- body

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pad
        spacing: 8

        TabBar {
            id: tabBar
            objectName: "tabBar"
            Layout.fillWidth: true
            background: Rectangle { color: "transparent" }

            Repeater {
                model: ["1. 설정", "2. 프로토콜", "3. 절차", "4. 검증", "5. 내보내기"]
                TabButton {
                    required property var modelData
                    text: modelData
                    font.pixelSize: 13
                    width: 150
                }
            }
        }

        StackLayout {
            id: pages
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            SetupPage {}
            ProtocolPage {}
            ProcedurePage {}
            ValidatePage {}
            ExportPage {}
        }
    }

    // ------------------------------------------------------------- footer

    footer: Rectangle {
        height: 30
        color: Theme.panel
        border.color: Theme.line
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.pad
            anchors.rightMargin: Theme.pad

            Text {
                text: workspace.statusText
                color: Theme.muted
                font.pixelSize: 11
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Text {
                visible: workspace.dirty
                text: "저장하지 않은 변경 있음"
                color: Theme.warn
                font.pixelSize: 11
            }
            Text {
                text: workspace.autosaveText
                color: Theme.muted
                font.pixelSize: 11
                leftPadding: 12
            }
        }
    }

    // ------------------------------------------------------------ dialogs

    FileDialog {
        id: openDialog
        title: "프로젝트 열기"
        nameFilters: ["PNE 스케줄 프로젝트 (*.schproj)", "모든 파일 (*)"]
        onAccepted: workspace.openPath(selectedFile)
    }

    FileDialog {
        id: saveDialog
        title: "다른 이름으로 저장"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "schproj"
        nameFilters: ["PNE 스케줄 프로젝트 (*.schproj)"]
        onAccepted: workspace.saveAs(selectedFile)
    }

    FolderDialog {
        id: folderDialog
        title: appWindow.pendingExport === "review_candidate"
               ? "검토용 후보를 저장할 폴더" : "미리보기를 저장할 폴더"
        onAccepted: {
            if (appWindow.pendingExport === "review_candidate")
                workspace.exportReviewCandidate(selectedFolder)
            else
                workspace.exportPreview(selectedFolder)
        }
    }

    MessageDialog {
        id: noticeDialog
        buttons: MessageDialog.Ok
    }

    MessageDialog {
        id: confirmDialog
        buttons: MessageDialog.Yes | MessageDialog.No
        onAccepted: {
            if (appWindow.pendingConfirm)
                appWindow.pendingConfirm()
            appWindow.pendingConfirm = null
        }
        onRejected: appWindow.pendingConfirm = null
    }

    MessageDialog {
        id: recoveryDialog
        title: "복구할 작업이 있습니다"
        text: "복구할 작업이 있습니다"
        informativeText: workspace.recoveryText + "\n\n마지막 자동 저장을 복구할까요?"
        buttons: MessageDialog.Yes | MessageDialog.No
        onAccepted: workspace.acceptRecovery()
        onRejected: workspace.discardRecovery()
    }

    Connections {
        target: workspace
        function onNotified(title, body, kind) { appWindow.showNotice(title, body, kind) }
    }

    // ---------------------------------------------------------- shortcuts

    Shortcut { sequence: StandardKey.Save; onActivated: appWindow.saveOrPrompt() }
    Shortcut { sequence: StandardKey.Open; onActivated: openDialog.open() }
    Shortcut { sequence: StandardKey.New; onActivated: workspace.newProject() }
    Shortcut { sequences: [StandardKey.Undo]; onActivated: workspace.undo() }
    Shortcut { sequences: [StandardKey.Redo]; onActivated: workspace.redo() }
    Shortcut { sequence: "Ctrl+1"; onActivated: appWindow.goToTab(0) }
    Shortcut { sequence: "Ctrl+2"; onActivated: appWindow.goToTab(1) }
    Shortcut { sequence: "Ctrl+3"; onActivated: appWindow.goToTab(2) }
    Shortcut { sequence: "Ctrl+4"; onActivated: appWindow.goToTab(3) }
    Shortcut { sequence: "Ctrl+5"; onActivated: appWindow.goToTab(4) }

    Component.onCompleted: if (workspace.hasRecovery) recoveryDialog.open()
}

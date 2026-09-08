import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 4. 검증 — every issue, and a double-click that lands on the input to fix.
Item {
    id: page
    property var rows: []
    property var notes: []
    property int errorCount: 0

    function reload() {
        rows = workspace.validationRows()
        notes = workspace.unverifiedNotes()
        var count = 0
        for (var i = 0; i < rows.length; ++i)
            if (rows[i].severity === "error")
                count += 1
        errorCount = count
    }

    Connections {
        target: workspace
        function onChanged() { page.reload() }
    }
    Component.onCompleted: reload()

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "오류 " + page.errorCount + "건 · 경고 " + (page.rows.length - page.errorCount) + "건"
                color: page.errorCount > 0 ? Theme.danger : Theme.accent
                font.pixelSize: 14
                font.bold: true
            }
            Text {
                text: "항목을 두 번 누르면 해당 입력 칸으로 이동합니다. 오류가 있어도 저장은 언제나 됩니다."
                color: Theme.muted
                font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
        }

        ListView {
            id: issueList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: page.rows
            spacing: 3
            ScrollBar.vertical: ScrollBar {}

            delegate: Rectangle {
                required property var modelData
                width: issueList.width
                height: issueRow.implicitHeight + 14
                radius: Theme.radius
                color: modelData.severity === "error" ? Theme.dangerSoft : Theme.warnSoft
                border.color: modelData.severity === "error" ? Theme.danger : Theme.warn
                border.width: 1

                RowLayout {
                    id: issueRow
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10

                    Text {
                        Layout.preferredWidth: 44
                        text: modelData.severityLabel
                        color: modelData.severity === "error" ? Theme.danger : Theme.warn
                        font.pixelSize: 12
                        font.bold: true
                    }
                    Text {
                        Layout.preferredWidth: 220
                        text: modelData.location
                        color: Theme.ink
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            Layout.fillWidth: true
                            text: modelData.message
                            color: Theme.ink
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: modelData.remediation.length > 0
                            text: "해결: " + modelData.remediation
                            color: Theme.muted
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }
                    }
                    Text {
                        Layout.preferredWidth: 130
                        text: modelData.code
                        color: Theme.muted
                        font.pixelSize: 11
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onDoubleClicked: {
                        if (modelData.moduleId.length === 0)
                            return
                        workspace.selectModule(modelData.moduleId)
                        appWindow.goToTab(1)
                    }
                }
            }
        }

        Card {
            Layout.fillWidth: true
            title: "미검증 근거"

            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 110
                clip: true
                Text {
                    text: page.notes.length ? page.notes.join("\n") : "구성된 실험이 없습니다."
                    color: Theme.muted
                    font.pixelSize: 11
                    font.family: "Menlo"
                }
            }
        }
    }
}

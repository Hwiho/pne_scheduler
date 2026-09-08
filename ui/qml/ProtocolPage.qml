import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 2. 프로토콜 — pick an experiment by purpose, then edit it as a real form.
Item {
    id: page
    property var goalRows: []
    property var moduleRows: []
    property var formData: ({ sections: [], derived: [], limitations: [] })
    property string impact: ""
    property string fieldError: ""
    property string erroredKey: ""

    function reload() {
        goalRows = workspace.goals(searchBox.text)
        moduleRows = workspace.moduleRows()
        formData = workspace.form()
    }

    Connections {
        target: workspace
        function onChanged() { page.reload() }
        function onSelectionChanged() { page.formData = workspace.form() }
    }
    Component.onCompleted: reload()

    SplitView {
        anchors.fill: parent
        orientation: Qt.Horizontal

        // ---------------------------------------------------- goal picker
        ColumnLayout {
            SplitView.preferredWidth: 320
            SplitView.minimumWidth: 260
            spacing: 8

            Text {
                text: "무엇을 알고 싶으신가요?"
                color: Theme.ink
                font.pixelSize: 14
                font.bold: true
            }

            TextField {
                id: searchBox
                Layout.fillWidth: true
                placeholderText: "예: 수명, 급속충전, QPEED"
                selectByMouse: true
                onTextChanged: page.goalRows = workspace.goals(text)
            }

            ListView {
                id: goalList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: page.goalRows
                spacing: 4
                ScrollBar.vertical: ScrollBar {}

                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: goalList.width
                    height: goalColumn.implicitHeight + 14
                    radius: Theme.radius
                    color: goalList.currentIndex === index ? Theme.accentSoft : Theme.panel
                    border.color: goalList.currentIndex === index ? Theme.accent : Theme.line

                    ColumnLayout {
                        id: goalColumn
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 2

                        Text {
                            text: modelData.title
                            color: Theme.ink
                            font.pixelSize: 13
                            font.bold: true
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            text: modelData.question
                            color: Theme.muted
                            font.pixelSize: 11
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: goalList.currentIndex = index
                        onDoubleClicked: page.addCurrentGoal()
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                visible: goalList.currentIndex >= 0 && page.goalRows.length > 0
                text: {
                    var goal = page.goalRows[goalList.currentIndex]
                    if (!goal) return ""
                    var parts = ["결과로 얻는 것: " + goal.outcome, "검증 상태: " + goal.trust]
                    if (goal.note) parts.push(goal.note)
                    return parts.join("\n")
                }
                color: Theme.muted
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            Button {
                Layout.fillWidth: true
                text: "이 실험 추가"
                enabled: page.goalRows.length > 0 && goalList.currentIndex >= 0
                onClicked: page.addCurrentGoal()
            }
        }

        // ------------------------------------------------- current phases
        ColumnLayout {
            SplitView.preferredWidth: 330
            SplitView.minimumWidth: 240
            spacing: 8

            Text {
                text: "현재 스케줄 구성"
                color: Theme.ink
                font.pixelSize: 14
                font.bold: true
            }

            ListView {
                id: moduleList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: page.moduleRows
                spacing: 4
                ScrollBar.vertical: ScrollBar {}

                delegate: Rectangle {
                    required property var modelData
                    width: moduleList.width
                    height: moduleColumn.implicitHeight + 14
                    radius: Theme.radius
                    color: modelData.moduleId === workspace.selectedModule ? Theme.accentSoft : Theme.panel
                    border.color: modelData.error ? Theme.danger
                                : modelData.moduleId === workspace.selectedModule ? Theme.accent : Theme.line

                    ColumnLayout {
                        id: moduleColumn
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 2

                        Text {
                            text: modelData.position + ". " + modelData.title
                            color: Theme.ink
                            font.pixelSize: 13
                            font.bold: true
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                        Text {
                            visible: modelData.subtitle.length > 0
                            text: modelData.subtitle
                            color: Theme.muted
                            font.pixelSize: 11
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            text: modelData.error
                                  ? "⚠ " + modelData.error
                                  : modelData.steps + " 스텝 · " + modelData.duration + " · " + modelData.trust
                            color: modelData.error ? Theme.danger : Theme.muted
                            font.pixelSize: 11
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: workspace.selectModule(modelData.moduleId)
                    }
                }
            }

            RowLayout {
                spacing: 6
                Button {
                    text: "복제"
                    enabled: workspace.selectedModule.length > 0
                    onClicked: workspace.duplicateSelected()
                }
                Button {
                    text: "삭제"
                    enabled: workspace.selectedModule.length > 0
                    onClicked: appWindow.confirm(
                        "구간 삭제",
                        workspace.selectedModule + " 구간을 삭제할까요?",
                        function () { workspace.removeSelected() })
                }
            }
        }

        // ------------------------------------------------------ the form
        ColumnLayout {
            SplitView.fillWidth: true
            SplitView.minimumWidth: 380
            spacing: 6

            Text {
                text: page.formData.title
                      ? page.formData.title + " · " + page.formData.moduleId
                      : "왼쪽에서 실험을 추가하거나 가운데에서 구간을 선택하세요"
                color: Theme.ink
                font.pixelSize: 14
                font.bold: true
                Layout.fillWidth: true
                elide: Text.ElideRight
            }

            Text {
                visible: page.formData.trust !== undefined
                text: {
                    var parts = []
                    if (page.formData.trust) parts.push("검증 상태: " + page.formData.trust)
                    if (page.formData.limitations && page.formData.limitations.length)
                        parts.push(page.formData.limitations.join(" · "))
                    return parts.join("  |  ")
                }
                color: Theme.muted
                font.pixelSize: 11
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            ScrollView {
                id: formScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                ColumnLayout {
                    width: formScroll.availableWidth
                    spacing: 10

                    Card {
                        Layout.fillWidth: true
                        title: "자동 계산"
                        visible: page.formData.derived && page.formData.derived.length > 0

                        Repeater {
                            model: page.formData.derived
                            Text {
                                required property var modelData
                                Layout.fillWidth: true
                                text: modelData.label + ": " + modelData.text
                                color: modelData.severity === "error" ? Theme.danger
                                     : modelData.severity === "warning" ? Theme.warn : Theme.ink
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    Repeater {
                        model: page.formData.sections

                        Card {
                            required property var modelData
                            Layout.fillWidth: true
                            title: modelData.title

                            Repeater {
                                model: modelData.fields

                                FieldRow {
                                    required property var modelData
                                    field: modelData
                                    siblingCount: page.formData.siblingCount
                                    localError: page.erroredKey === modelData.key ? page.fieldError : ""
                                    onCommit: function (key, value) { page.commitField(key, value) }
                                    onApplyAll: function (key, value) { page.applyAll(key, value) }
                                }
                            }
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                visible: page.impact.length > 0
                text: page.impact
                color: Theme.accent
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
        }
    }

    function addCurrentGoal() {
        var goal = page.goalRows[goalList.currentIndex]
        if (!goal)
            return
        var result = workspace.addGoal(goal.goalId)
        if (!result.ok)
            appWindow.showNotice("추가할 수 없습니다", result.message, "error")
    }

    function commitField(key, value) {
        var result = workspace.setParam(key, value)
        if (result.ok) {
            page.fieldError = ""
            page.erroredKey = ""
            page.impact = result.message
        } else {
            page.fieldError = result.message
            page.erroredKey = key
        }
    }

    function applyAll(key, value) {
        appWindow.confirm(
            "모두 적용",
            "이 값을 같은 종류의 구간 " + page.formData.siblingCount + "개에 모두 적용할까요?",
            function () {
                var result = workspace.applyToAll(key, value)
                if (!result.ok)
                    appWindow.showNotice("적용할 수 없습니다", result.message, "error")
                else
                    page.impact = result.message
            })
    }
}

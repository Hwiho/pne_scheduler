import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 3. 절차 — the run order as a timeline, plus the read-only expanded steps.
Item {
    id: page
    property var phases: []
    property var steps: []
    property var budget: ({ ok: false, notes: [], errors: [] })
    property var stepRows: []
    property var stepKinds: []

    function reload() {
        phases = workspace.phases()
        steps = workspace.stepRows()
        stepRows = workspace.customStepRows()
        if (stepKinds.length === 0)
            stepKinds = workspace.stepKindChoices()
    }

    function solveBudget() {
        budget = workspace.cyclesWithin(parseFloat(budgetDaysField.text) || 0,
                                        parseInt(budgetStepField.text) || 1)
    }

    Connections {
        target: workspace
        function onChanged() { page.reload() }
        function onSelectionChanged() { page.stepRows = workspace.customStepRows() }
    }
    Component.onCompleted: reload()

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        Text {
            text: "실제 실행 순서입니다. 위/아래 버튼으로 옮길 수 있고, 각 구간이 몇 번 스텝인지 함께 표시됩니다."
            color: Theme.muted
            font.pixelSize: 12
        }

        // Cycle counts are chosen backwards: the cell has to come off the
        // cycler by a date, and the question is what fits. This asks the same
        // estimator the summary uses, so RPT blocks and rests are counted.
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "기간으로 정하기"
                color: Theme.ink
                font.pixelSize: 12
                font.bold: true
            }
            TextField {
                id: budgetDaysField
                Layout.preferredWidth: 60
                text: "14"
                selectByMouse: true
                onEditingFinished: page.solveBudget()
            }
            Text { text: "일 안에"; color: Theme.muted; font.pixelSize: 11 }
            TextField {
                id: budgetStepField
                Layout.preferredWidth: 50
                text: "50"
                selectByMouse: true
                onEditingFinished: page.solveBudget()
            }
            Text { text: "사이클 단위로"; color: Theme.muted; font.pixelSize: 11 }
            Button {
                text: "계산"
                onClicked: page.solveBudget()
            }
            Button {
                text: page.budget.ok ? page.budget.totalCycles + " 사이클로 맞추기" : "맞추기"
                enabled: page.budget.ok === true
                onClicked: {
                    workspace.applyCycleCount(page.budget.totalCycles)
                    page.budget = ({ ok: false, notes: [], errors: [] })
                }
            }
            Text {
                Layout.fillWidth: true
                text: page.budget.errors && page.budget.errors.length
                      ? page.budget.errors.join(" ")
                      : (page.budget.text || "")
                color: (page.budget.errors && page.budget.errors.length)
                       ? Theme.danger : Theme.muted
                font.pixelSize: 11
                elide: Text.ElideRight
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(200, page.height * 0.42)
            spacing: 8

            ListView {
                id: phaseList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: page.phases
                spacing: 4
                ScrollBar.vertical: ScrollBar {}

                delegate: Rectangle {
                    required property var modelData
                    width: phaseList.width
                    height: 62
                    radius: Theme.radius
                    color: modelData.moduleId === workspace.selectedModule ? Theme.accentSoft : Theme.panel
                    border.color: modelData.error ? Theme.danger
                                : modelData.moduleId === workspace.selectedModule ? Theme.accent : Theme.line

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 12

                        Rectangle {
                            Layout.preferredWidth: 30
                            Layout.preferredHeight: 30
                            radius: 15
                            color: Theme.accent
                            Text {
                                anchors.centerIn: parent
                                text: modelData.position
                                color: "#ffffff"
                                font.pixelSize: 13
                                font.bold: true
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text {
                                text: modelData.title
                                color: Theme.ink
                                font.pixelSize: 13
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            Text {
                                text: modelData.error ? "⚠ " + modelData.error : modelData.subtitle
                                color: modelData.error ? Theme.danger : Theme.muted
                                font.pixelSize: 11
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }

                        Text {
                            Layout.preferredWidth: 110
                            text: modelData.range + " 스텝"
                            color: Theme.ink
                            font.pixelSize: 12
                        }
                        Text {
                            Layout.preferredWidth: 120
                            text: modelData.duration
                            color: Theme.ink
                            font.pixelSize: 12
                        }
                        Text {
                            Layout.preferredWidth: 140
                            text: modelData.trust
                            color: Theme.muted
                            font.pixelSize: 11
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: workspace.selectModule(modelData.moduleId)
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 200
                Layout.alignment: Qt.AlignTop
                spacing: 6

                Button {
                    Layout.fillWidth: true
                    text: "▲ 위로"
                    enabled: workspace.selectedModule.length > 0
                    onClicked: workspace.moveSelected(-1)
                }
                Button {
                    Layout.fillWidth: true
                    text: "▼ 아래로"
                    enabled: workspace.selectedModule.length > 0
                    onClicked: workspace.moveSelected(1)
                }
                Button {
                    Layout.fillWidth: true
                    text: "개별 스텝으로 분리"
                    enabled: workspace.selectedModule.length > 0
                    onClicked: appWindow.confirm(
                        "개별 스텝으로 분리",
                        "이 구간을 지금 값 그대로 펼쳐서 개별 스텝으로 바꿉니다.\n" +
                        "이후에는 프리셋 검증 상태가 아니라 '직접 편집' 상태가 됩니다. 계속할까요?",
                        function () { workspace.detachSelected() })
                }
                Text {
                    Layout.fillWidth: true
                    text: workspace.canEditSteps()
                          ? "이 구간은 직접 편집 상태입니다. 아래에서 스텝을 고칠 수 있습니다."
                          : "분리하면 프리셋 보장이 사라지고 직접 편집한 스텝이 됩니다."
                    color: Theme.muted
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                }
            }
        }

        // Only a detached module exposes its steps; a preset shows nothing here
        // because editing one in place would break the golden-topology claim.
        Card {
            Layout.fillWidth: true
            visible: page.stepRows.length > 0
            title: "개별 스텝 편집 · " + page.stepRows.length + "개"

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: newStepKind
                    Layout.preferredWidth: 200
                    textRole: "title"
                    valueRole: "kind"
                    model: page.stepKinds
                }
                Button {
                    text: "맨 뒤에 추가"
                    onClicked: workspace.insertStep(page.stepRows.length,
                                                    newStepKind.currentValue)
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "END 는 항상 마지막이며 구간을 비울 수 없습니다."
                    color: Theme.muted
                    font.pixelSize: 10
                }
            }

            Repeater {
                model: page.stepRows

                Rectangle {
                    id: stepCard
                    required property var modelData
                    // The inner Repeater's delegate shadows `modelData`, so the
                    // step's own index is held here where the fields can reach it.
                    readonly property int stepIndex: modelData.index
                    Layout.fillWidth: true
                    implicitHeight: stepBody.implicitHeight + 12
                    radius: 6
                    color: Theme.panelAlt
                    border.color: Theme.line

                    ColumnLayout {
                        id: stepBody
                        x: 8
                        y: 6
                        width: parent.width - 16
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text {
                                text: stepCard.modelData.number + ". " + stepCard.modelData.stepType
                                      + (stepCard.modelData.mode ? " · " + stepCard.modelData.mode : "")
                                color: Theme.ink
                                font.pixelSize: 12
                                font.bold: true
                            }
                            Text {
                                Layout.fillWidth: true
                                text: stepCard.modelData.label
                                color: Theme.muted
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                            Button {
                                text: "▲"
                                onClicked: workspace.moveStep(stepCard.stepIndex, -1)
                            }
                            Button {
                                text: "▼"
                                onClicked: workspace.moveStep(stepCard.stepIndex, 1)
                            }
                            Button {
                                text: "＋"
                                onClicked: workspace.insertStep(stepCard.stepIndex + 1,
                                                                newStepKind.currentValue)
                            }
                            Button {
                                text: "삭제"
                                onClicked: workspace.removeStep(stepCard.stepIndex)
                            }
                        }

                        Flow {
                            Layout.fillWidth: true
                            spacing: 8

                            Repeater {
                                model: stepCard.modelData.fields

                                RowLayout {
                                    id: fieldRow
                                    required property var modelData
                                    spacing: 4
                                    Text {
                                        text: fieldRow.modelData.label
                                        color: Theme.muted
                                        font.pixelSize: 10
                                    }
                                    TextField {
                                        Layout.preferredWidth: 96
                                        text: fieldRow.modelData.text
                                        font.pixelSize: 11
                                        selectByMouse: true
                                        onEditingFinished: if (text !== fieldRow.modelData.text)
                                            workspace.setStepField(stepCard.stepIndex,
                                                                   fieldRow.modelData.key, text)
                                    }
                                    Text {
                                        visible: fieldRow.modelData.detail.length > 0
                                        text: fieldRow.modelData.detail
                                        color: Theme.muted
                                        font.pixelSize: 10
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Text {
            text: "장비 상세 보기 (읽기 전용) · " + page.steps.length + " 스텝"
            color: Theme.ink
            font.pixelSize: 13
            font.bold: true
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.panel
            radius: Theme.radius
            border.color: Theme.line

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 1
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28
                    color: Theme.panelAlt
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 6
                        Repeater {
                            model: [
                                { label: "번호", width: 50 },
                                { label: "구간", width: 150 },
                                { label: "종류", width: 90 },
                                { label: "모드", width: 60 },
                                { label: "전류", width: 150 },
                                { label: "전압", width: 200 },
                                { label: "종료 조건", width: 190 },
                                { label: "LOOP", width: 110 }
                            ]
                            Text {
                                required property var modelData
                                Layout.preferredWidth: modelData.width
                                text: modelData.label
                                color: Theme.muted
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                        Item { Layout.fillWidth: true }
                    }
                }

                ListView {
                    id: stepList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: page.steps
                    ScrollBar.vertical: ScrollBar {}

                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: stepList.width
                        height: 24
                        color: index % 2 === 0 ? Theme.panel : Theme.bg

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 6
                            Repeater {
                                model: [
                                    { value: modelData.number, width: 50 },
                                    { value: modelData.phase, width: 150 },
                                    { value: modelData.type, width: 90 },
                                    { value: modelData.mode, width: 60 },
                                    { value: modelData.current, width: 150 },
                                    { value: modelData.voltage, width: 200 },
                                    { value: modelData.end, width: 190 },
                                    { value: modelData.loop, width: 110 }
                                ]
                                Text {
                                    required property var modelData
                                    Layout.preferredWidth: modelData.width
                                    text: modelData.value
                                    color: Theme.ink
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                            }
                            Item { Layout.fillWidth: true }
                        }
                    }
                }
            }
        }
    }
}
